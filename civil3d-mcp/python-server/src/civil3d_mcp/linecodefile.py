"""
Line code file parser for Civil 3D feature generation.

Supported file formats:
  .json  — native format (see schema below)
  .csv   — simple comma-delimited: code, layer, color, linetype, include_in_tin

JSON schema
───────────
{
  "version": "1.0",
  "default_layer": "C-SURV-FTRE",
  "codes": [
    {
      "code":          "SFSL",           // feature code matched against point descriptions
      "description":   "Surface Level",  // human-readable label (optional)
      "layer":         "C-SURV-FTRE",   // AutoCAD layer for the polyline
      "color":         1,               // AutoCAD colour index 1-256 (optional)
      "linetype":      "Continuous",    // linetype name (optional)
      "include_in_tin": true,           // whether 3-D polyline is used as TIN breakline
      "draw_as":       "3d_polyline"    // "3d_polyline" or "feature_line"
    }
  ]
}

The CSV format recognises columns in this order (header optional):
  code, layer, color, linetype, include_in_tin
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


# ── Data model ────────────────────────────────────────────────────────────────

class CodeDef:
    __slots__ = (
        "code", "description", "layer", "color",
        "linetype", "include_in_tin", "draw_as",
    )

    def __init__(self, **kw: Any) -> None:
        self.code          = str(kw.get("code", ""))
        self.description   = str(kw.get("description", ""))
        self.layer         = str(kw.get("layer", "C-SURV-FTRE"))
        self.color         = int(kw["color"]) if "color" in kw and kw["color"] else None
        self.linetype      = str(kw.get("linetype", "Continuous"))
        self.include_in_tin = bool(kw.get("include_in_tin", True))
        self.draw_as       = str(kw.get("draw_as", "3d_polyline"))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code":          self.code,
            "description":   self.description,
            "layer":         self.layer,
            "linetype":      self.linetype,
            "include_in_tin": self.include_in_tin,
            "draw_as":       self.draw_as,
        }
        if self.color is not None:
            d["color"] = self.color
        return d


class LineCodeFile:
    def __init__(self, codes: list[CodeDef], default_layer: str = "C-SURV-FTRE") -> None:
        self.codes: dict[str, CodeDef] = {c.code.upper(): c for c in codes}
        self.default_layer = default_layer

    def get(self, code: str) -> CodeDef | None:
        return self.codes.get(code.upper())

    # Returns the code_styles dict expected by the C# create_figures tool
    def to_code_styles(self) -> dict[str, dict[str, Any]]:
        result = {}
        for code, cd in self.codes.items():
            entry: dict[str, Any] = {"layer": cd.layer}
            if cd.color is not None:
                entry["color"] = cd.color
            result[code] = entry
        return result

    # Returns only codes that participate in TIN as breaklines
    def tin_codes(self) -> list[str]:
        return [c.code for c in self.codes.values() if c.include_in_tin]

    def summary(self) -> dict[str, Any]:
        return {
            "total_codes": len(self.codes),
            "tin_codes": self.tin_codes(),
            "codes": [c.to_dict() for c in self.codes.values()],
        }


# ── Loaders ───────────────────────────────────────────────────────────────────

def load(path: str | Path) -> LineCodeFile:
    """Load a line code file (.json or .csv). Raises ValueError for unknown types."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        return _load_json(p)
    if p.suffix.lower() == ".csv":
        return _load_csv(p)
    raise ValueError(f"Unsupported line code file type: {p.suffix!r}")


def _load_json(path: Path) -> LineCodeFile:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    default_layer = raw.get("default_layer", "C-SURV-FTRE")
    codes = [CodeDef(**entry) for entry in raw.get("codes", [])]
    return LineCodeFile(codes, default_layer)


def _load_csv(path: Path) -> LineCodeFile:
    codes: list[CodeDef] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            # Has header row
            for row in reader:
                row_lower = {k.strip().lower(): v.strip() for k, v in row.items()}
                _normalise_csv_row(row_lower)
                codes.append(CodeDef(**row_lower))
        else:
            # No header — positional: code, layer, color, linetype, include_in_tin
            f.seek(0)
            for cols in csv.reader(f):
                if not cols or not cols[0].strip():
                    continue
                kw: dict[str, Any] = {"code": cols[0].strip()}
                if len(cols) > 1: kw["layer"]        = cols[1].strip()
                if len(cols) > 2: kw["color"]        = cols[2].strip() or None
                if len(cols) > 3: kw["linetype"]     = cols[3].strip()
                if len(cols) > 4: kw["include_in_tin"] = cols[4].strip().lower() not in ("0","false","no")
                codes.append(CodeDef(**kw))
    return LineCodeFile(codes)


def _normalise_csv_row(row: dict[str, str]) -> None:
    """Normalise CSV header aliases in place."""
    _alias = {
        "feature_code": "code", "feature": "code",
        "tin": "include_in_tin", "breakline": "include_in_tin",
        "col": "color", "colour": "color",
    }
    for alias, canonical in _alias.items():
        if alias in row and canonical not in row:
            row[canonical] = row.pop(alias)
