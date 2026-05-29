"""
Surveyor GNSS field CSV processor for Civil 3D point import.

Column layout (no header row, comma-delimited):
  0     : point_no     (may start with BOM or contain non-numeric chars → stripped)
  1     : easting      (local grid E, metres)
  2     : northing     (local grid N, metres)
  3     : elevation    (metres AHD / local datum)
  4     : code         (feature code, e.g. RDCR, SFSL, STFNX …)
  5-14  : attr1–10     (optional attributes; actual count varies by export)
           GPS boundary detected automatically by first column containing a
           degree sign (°) — everything up to that column (max 10) is attrs.
  col N+: GPS metadata (lat, lon, ellipsoidal h, precision, …) → ignored

Duplicate rules:
  Same cleaned point number, 3-D distance < threshold (default 3 mm):
    • If older has no attrs but newer does → keep newer (better data)
    • Otherwise keep older (first observation wins)
  Same cleaned point number, distance ≥ threshold:
    → both are valid; older keeps original number, newer gets next free integer.

Non-numeric point names: strip all non-digit characters (also strips BOM).
  Names that are entirely non-numeric are warned and skipped.

Output: PENZD ASCII CSV, no BOM, CRLF line endings.
  Format: PointNo, Easting, Northing, Elevation, Description
"""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .csv_utils import detect_encoding

DUPLICATE_THRESHOLD_DEFAULT_MM = 3.0
_DMS_RE = re.compile(r'[°°°]')      # degree sign variants


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SurveyPoint:
    raw_no: str
    point_no: int
    easting: float
    northing: float
    elevation: float
    code: str
    attrs: list[str]       # non-empty attribute strings only (for display)
    source_row: int        # 1-based row index in input file


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_pt_no(raw: str) -> str | None:
    """Strip all non-digit characters (including BOM). None if nothing left."""
    digits = re.sub(r'[^0-9]', '', raw.strip())
    return digits if digits else None


def _detect_attr_count(row: list[str]) -> int:
    """
    Return how many attribute columns exist in a row, by scanning from col 5
    for the first GPS column (contains degree sign).  Caps at 10.
    """
    for i in range(5, min(5 + 10, len(row))):
        if _DMS_RE.search(row[i]):
            return i - 5
    return min(10, max(0, len(row) - 5))


def _has_attrs(attrs: list[str]) -> bool:
    return any(attrs)


def _dist3d(a: SurveyPoint, b: SurveyPoint) -> float:
    return math.sqrt(
        (a.easting  - b.easting)  ** 2 +
        (a.northing - b.northing) ** 2 +
        (a.elevation - b.elevation) ** 2
    )


# ── Parsing ───────────────────────────────────────────────────────────────────

def parse_surveyor_csv(
    path: str | Path,
    encoding: str | None = None,
) -> tuple[list[SurveyPoint], int, list[str]]:
    """
    Read and parse the surveyor GNSS CSV.

    Returns:
        (points, attr_count_detected, warnings)
    """
    enc = encoding or detect_encoding(path)
    # Always use utf-8-sig to strip any BOM regardless of what detect_encoding says
    if enc in ('utf-8', 'utf-8-sig'):
        enc = 'utf-8-sig'

    points: list[SurveyPoint] = []
    warnings: list[str] = []
    attr_count: int | None = None

    with open(path, newline='', encoding=enc, errors='replace') as f:
        reader = csv.reader(f)
        for row_idx, row in enumerate(reader, start=1):
            if not row or all(c.strip() == '' for c in row):
                continue

            raw_no = row[0].strip()

            # Header-row detection: if first cell can't yield a number, skip
            if _clean_pt_no(raw_no) is None:
                warnings.append(f"Row {row_idx}: skipped — looks like a header: {row[:5]}")
                continue

            cleaned = _clean_pt_no(raw_no)
            if cleaned is None:
                warnings.append(
                    f"Row {row_idx}: non-numeric point name '{raw_no}' — skipped"
                )
                continue

            try:
                e = float(row[1])
                n = float(row[2])
                z = float(row[3])
            except (IndexError, ValueError) as ex:
                warnings.append(f"Row {row_idx}: bad coordinate ({ex}) — skipped")
                continue

            # Detect attribute column count from first data row
            if attr_count is None:
                attr_count = _detect_attr_count(row)

            code = row[4].strip() if len(row) > 4 else ''
            attrs = [
                row[5 + i].strip()
                for i in range(attr_count or 0)
                if len(row) > 5 + i and row[5 + i].strip()
            ]

            points.append(SurveyPoint(
                raw_no=raw_no,
                point_no=int(cleaned),
                easting=e,
                northing=n,
                elevation=z,
                code=code,
                attrs=attrs,
                source_row=row_idx,
            ))

    return points, (attr_count or 0), warnings


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate(
    points: list[SurveyPoint],
    threshold_mm: float = DUPLICATE_THRESHOLD_DEFAULT_MM,
) -> tuple[list[SurveyPoint], list[str]]:
    """
    Resolve duplicate point numbers.  Returns (cleaned_list, report_lines).
    """
    threshold_m = threshold_mm / 1000.0

    groups: dict[int, list[SurveyPoint]] = defaultdict(list)
    for pt in points:
        groups[pt.point_no].append(pt)

    used: set[int] = set(groups.keys())

    def next_free() -> int:
        n = max(used) + 1
        while n in used:
            n += 1
        used.add(n)
        return n

    result: list[SurveyPoint] = []
    report: list[str] = []

    for pt_no in sorted(groups.keys()):
        group = groups[pt_no]

        if len(group) == 1:
            result.append(group[0])
            continue

        kept = group[0]
        for later in group[1:]:
            dist = _dist3d(kept, later)
            if dist < threshold_m:
                if not _has_attrs(kept.attrs) and _has_attrs(later.attrs):
                    report.append(
                        f"Pt {pt_no} (rows {kept.source_row}+{later.source_row}): "
                        f"same location ({dist*1000:.2f} mm) — "
                        f"replaced with row {later.source_row} (has attributes)"
                    )
                    kept = later
                else:
                    report.append(
                        f"Pt {pt_no} (rows {kept.source_row}+{later.source_row}): "
                        f"same location ({dist*1000:.2f} mm) — "
                        f"row {later.source_row} discarded"
                    )
            else:
                new_no = next_free()
                report.append(
                    f"Pt {pt_no} (rows {kept.source_row}+{later.source_row}): "
                    f"CONFLICT — distance {dist*1000:.1f} mm > {threshold_mm:.0f} mm — "
                    f"row {later.source_row} renamed to point {new_no}"
                )
                later.point_no = new_no
                result.append(later)

        result.append(kept)

    result.sort(key=lambda p: p.point_no)
    return result, report


# ── Writer ────────────────────────────────────────────────────────────────────

def _build_desc(pt: SurveyPoint) -> str:
    parts = [pt.code] if pt.code else []
    parts.extend(pt.attrs)
    return ' '.join(parts)


def write_penzd(points: list[SurveyPoint], output_path: str | Path) -> None:
    """
    Write PENZD ASCII CSV (Civil 3D import format):
      PointNo, Easting, Northing, Elevation, Description
    No BOM, CRLF line endings.
    """
    # newline='' suppresses Python's own translation so csv.writer's
    # default lineterminator='\r\n' produces clean CRLF on all platforms.
    with open(output_path, 'w', newline='',
              encoding='ascii', errors='replace') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for pt in points:
            writer.writerow([
                pt.point_no,
                f'{pt.easting:.3f}',
                f'{pt.northing:.3f}',
                f'{pt.elevation:.3f}',
                _build_desc(pt),
            ])


# ── Full pipeline ─────────────────────────────────────────────────────────────

def process_surveyor_pipeline(
    input_path: str | Path,
    output_path: str | Path,
    threshold_mm: float = 3.0,
    encoding: str | None = None,
) -> dict[str, Any]:
    """
    Full pipeline:
      parse → clean point numbers → deduplicate → write PENZD CSV

    Returns a report dict with statistics and warnings.
    """
    raw_pts, attr_count, parse_warnings = parse_surveyor_csv(
        input_path, encoding
    )
    clean_pts, dup_report = deduplicate(raw_pts, threshold_mm=threshold_mm)

    discarded = len(raw_pts) - len(clean_pts)
    write_penzd(clean_pts, output_path)

    code_counts: dict[str, int] = {}
    for pt in clean_pts:
        key = pt.code or '(blank)'
        code_counts[key] = code_counts.get(key, 0) + 1

    return {
        'encoding_detected': detect_encoding(input_path),
        'attribute_columns_detected': attr_count,
        'rows_input': len(raw_pts),
        'rows_output': len(clean_pts),
        'rows_discarded': discarded,
        'parse_warnings': parse_warnings,
        'duplicate_report': dup_report,
        'code_summary': dict(sorted(code_counts.items())),
        'output_path': str(output_path),
    }
