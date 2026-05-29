"""
CSV processing utilities for Civil 3D point import.

Handles:
- Auto-detecting file encoding (UTF-8 / ASCII / GBK / latin-1)
- Normalising column layout to PNEZD / PENZD order
- Injecting BEGIN / END line-code markers into point descriptions
- Writing output as plain ASCII (latin-1) CSV
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── encoding detection ────────────────────────────────────────────────────────

_BOM_MAP = {
    b"\xef\xbb\xbf": "utf-8-sig",
    b"\xff\xfe":     "utf-16-le",
    b"\xfe\xff":     "utf-16-be",
}

_CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1", "ascii"]


def detect_encoding(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    for bom, enc in _BOM_MAP.items():
        if raw.startswith(bom):
            return enc
    for enc in _CANDIDATE_ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


# ── column normalisation ───────────────────────────────────────────────────────

# Common header aliases → canonical name
_ALIASES: dict[str, str] = {
    # point number
    "pointno": "point_no", "ptno": "point_no", "id": "point_no",
    "point": "point_no", "no": "point_no", "num": "point_no",
    # easting (X)
    "easting": "x", "e": "x",
    # northing (Y)
    "northing": "y", "n": "y",
    # elevation / Z
    "elevation": "z", "elev": "z", "height": "z", "h": "z",
    # description / code
    "description": "desc", "code": "desc", "feature": "desc",
    "linecode": "desc", "line_code": "desc",
}


def _normalise_header(col: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", col.lower())
    return _ALIASES.get(key, col.lower())


def read_csv(path: str | Path, encoding: str | None = None) -> tuple[list[str], list[dict]]:
    """Return (headers, rows-as-dicts) with normalised column names."""
    enc = encoding or detect_encoding(path)
    with open(path, newline="", encoding=enc, errors="replace") as f:
        reader = csv.DictReader(f)
        raw_headers = reader.fieldnames or []
        norm_headers = [_normalise_header(h) for h in raw_headers]
        rows = []
        for row in reader:
            rows.append({norm_headers[i]: v.strip()
                         for i, v in enumerate(row.values())})
    return norm_headers, rows


# ── line-code / figure marker injection ───────────────────────────────────────

# Civil 3D figure-code convention (FDOT / standard surveyors):
#   description starts with  <CODE>.B  → begin figure named CODE
#   description is           <CODE>    → continue figure
#   description ends with    <CODE>.E  → end figure
#
# We use the compact prefix form that Civil 3D Description Key Sets understand:
#   .B<CODE>   begin
#   <CODE>     continue
#   .E<CODE>   end

def inject_line_codes(rows: list[dict]) -> list[dict]:
    """
    Analyse the 'desc' column.  For each contiguous run of rows sharing the
    same code, prepend '.B' to the first and '.E' to the last so Civil 3D
    will stitch them into a figure automatically.

    Rows without a 'desc' value, or with a purely numeric description, are
    treated as isolated topo shots and left unchanged.
    """
    # Group consecutive rows by (code, order) into runs
    result = [dict(r) for r in rows]
    n = len(result)
    i = 0
    while i < n:
        code = result[i].get("desc", "").strip()
        if not code or code.isdigit():
            i += 1
            continue
        # find the end of this run (same code, consecutive)
        j = i + 1
        while j < n and result[j].get("desc", "").strip() == code:
            j += 1
        run_len = j - i
        if run_len == 1:
            # single point — leave untouched (no figure)
            i = j
            continue
        # mark begin / end
        result[i]["desc"]     = f".B{code}"
        result[j - 1]["desc"] = f".E{code}"
        i = j
    return result


# ── PNEZD writer ──────────────────────────────────────────────────────────────

def to_pnezd_rows(rows: list[dict]) -> list[list[str]]:
    """Return rows in [PointNo, Northing, Easting, Elevation, Description] order."""
    out = []
    for i, r in enumerate(rows):
        pn   = r.get("point_no", str(i + 1))
        x    = r.get("x",  r.get("easting",  "0"))
        y    = r.get("y",  r.get("northing", "0"))
        z    = r.get("z",  r.get("elevation", "0"))
        desc = r.get("desc", "")
        out.append([pn, y, x, z, desc])   # PNEZD: pt, N, E, Z, D
    return out


def write_ascii_csv(rows_pnezd: list[list[str]], output_path: str | Path) -> None:
    """Write to ASCII (latin-1) CSV, no BOM, CRLF line endings (Civil 3D default)."""
    with open(output_path, "w", newline="\r\n", encoding="ascii",
              errors="replace") as f:
        writer = csv.writer(f)
        for row in rows_pnezd:
            writer.writerow(row)


# ── full pipeline ──────────────────────────────────────────────────────────────

def process_pipeline(
    input_path: str,
    output_path: str,
    format_out: str = "PNEZD",
    inject_codes: bool = True,
    input_encoding: str | None = None,
) -> dict[str, Any]:
    enc = input_encoding or detect_encoding(input_path)
    headers, rows = read_csv(input_path, enc)

    if inject_codes:
        rows = inject_line_codes(rows)

    pnezd = to_pnezd_rows(rows)
    write_ascii_csv(pnezd, output_path)

    return {
        "input_encoding": enc,
        "rows_processed": len(rows),
        "output_path": str(output_path),
        "format": format_out,
        "columns_detected": headers,
    }


# ── external script runner ────────────────────────────────────────────────────

def run_external(cmd: list[str], cwd: str | None = None,
                 timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Timeout exceeded"}
    except FileNotFoundError as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}
