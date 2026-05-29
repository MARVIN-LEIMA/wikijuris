"""
MCP tools for the full CSV → point-import → linework pipeline.

Flow:
  1. process_csv_file       — read raw CSV, inject line codes, write ASCII output
  2. import_points_from_csv — load the processed CSV into Civil 3D COGO points
  3. create_figures          — connect same-coded points into feature lines
  4. create_point_group      — filter / group COGO points by description
"""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge
from .. import csv_utils
from .. import surveyor_csv as scsv
from .. import linecodefile as lcf


def register(app: Server) -> None:

    # ── 1. CSV processing (pure Python, no Civil 3D needed) ─────────────────

    @app.tool()
    async def process_csv_file(
        input_path: str,
        output_path: str,
        inject_line_codes: bool = True,
        input_encoding: str | None = None,
    ) -> list[TextContent]:
        """
        Read a survey CSV file, add Civil 3D figure line-code markers, and
        write an ASCII PNEZD CSV ready for Civil 3D point import.

        Supported input column orders (auto-detected from headers):
        - PointNo, X/Easting, Y/Northing, Z/Elevation, Description/Code
        - Any order — columns are matched by name.

        Line-code injection:
        Consecutive points sharing the same description code are bracketed
        with .B<CODE> (begin) and .E<CODE> (end) so Civil 3D automatically
        connects them into a figure / feature line.

        Args:
            input_path:        Full path to the input CSV (UTF-8 or ASCII).
            output_path:       Full path for the output ASCII CSV.
            inject_line_codes: Add .B/.E figure markers (default True).
            input_encoding:    Force encoding, e.g. "utf-8" or "gbk".
                               Auto-detected if omitted.
        """
        result = csv_utils.process_pipeline(
            input_path=input_path,
            output_path=output_path,
            inject_codes=inject_line_codes,
            input_encoding=input_encoding,
        )
        lines = [
            f"Input encoding : {result['input_encoding']}",
            f"Columns found  : {', '.join(result['columns_detected'])}",
            f"Rows processed : {result['rows_processed']}",
            f"Output         : {result['output_path']}",
        ]
        return [TextContent(type="text", text="\n".join(lines))]

    # ── 2. Import points into Civil 3D ───────────────────────────────────────

    @app.tool()
    async def import_points_from_csv(
        csv_path: str,
        format: str = "PNEZD",
        point_group: str | None = None,
        add_to_drawing: bool = True,
    ) -> list[TextContent]:
        """
        Import COGO points from a CSV file into the active Civil 3D drawing.

        The CSV must be in PNEZD format (PointNo, Northing, Easting, Elevation,
        Description). Use process_csv_file first to convert raw survey exports.

        Args:
            csv_path:      Full path to the ASCII CSV file.
            format:        "PNEZD" (default) or "PENZD".
            point_group:   Name of a point group to add imported points into.
                           Creates the group if it doesn't exist.
            add_to_drawing: Display points in the drawing (default True).
        """
        params: dict = {
            "csv_path": csv_path,
            "format": format,
            "add_to_drawing": add_to_drawing,
        }
        if point_group:
            params["point_group"] = point_group

        result = await bridge.call("import_points", params)
        return [TextContent(type="text", text=f"Points imported: {result}")]

    # ── 3. Create figures / feature lines from point codes ───────────────────

    @app.tool()
    async def create_figures_from_points(
        layer: str = "C-SURV-FTRE",
        site: str | None = None,
        codes: list[str] | None = None,
    ) -> list[TextContent]:
        """
        Connect COGO points that carry .B/.E figure codes into Civil 3D
        feature lines (or polylines if no site is specified).

        Points must already be imported (use import_points_from_csv first).
        The description codes .B<CODE> … <CODE> … .E<CODE> are used to
        group and sequence the points.

        Args:
            layer:  AutoCAD layer for the resulting feature lines.
            site:   Civil 3D site name for feature lines (optional; plain
                    polylines are drawn when omitted).
            codes:  List of specific codes to process, e.g. ["EP","CL"].
                    All coded points are processed when omitted.
        """
        params: dict = {"layer": layer}
        if site:
            params["site"] = site
        if codes:
            params["codes"] = codes

        result = await bridge.call("create_figures", params)
        return [TextContent(type="text", text=f"Figures created: {result}")]

    # ── 4. Point group ───────────────────────────────────────────────────────

    @app.tool()
    async def create_point_group(
        name: str,
        description: str = "",
        include_codes: list[str] | None = None,
        exclude_codes: list[str] | None = None,
        include_point_numbers: str | None = None,
    ) -> list[TextContent]:
        """
        Create or update a Civil 3D point group to filter COGO points.

        Args:
            name:                  Point group name.
            description:           Optional description.
            include_codes:         List of description codes to include,
                                   e.g. ["EP", "CL", "TC"].
            exclude_codes:         List of description codes to exclude.
            include_point_numbers: Point number range string, e.g. "1-500,750".
        """
        params: dict = {"name": name, "description": description}
        if include_codes:
            params["include_codes"] = include_codes
        if exclude_codes:
            params["exclude_codes"] = exclude_codes
        if include_point_numbers:
            params["include_point_numbers"] = include_point_numbers

        result = await bridge.call("create_point_group", params)
        return [TextContent(type="text", text=f"Point group: {result}")]

    # ── 5. Surveyor GNSS CSV processor ───────────────────────────────────────

    @app.tool()
    async def process_surveyor_csv(
        input_path: str,
        output_path: str,
        duplicate_threshold_mm: float = 3.0,
        input_encoding: str | None = None,
    ) -> list[TextContent]:
        """
        Process a GNSS surveyor CSV file and write a Civil 3D-ready PENZD CSV.

        Expected input format (no header, comma-delimited):
          Col 0  : Point number (integer; non-numeric chars are stripped)
          Col 1  : Easting  (local grid, metres)
          Col 2  : Northing (local grid, metres)
          Col 3  : Elevation (metres)
          Col 4  : Feature code (e.g. RDCR, SFSL, STFNX)
          Col 5+ : Up to 10 optional attributes, then GPS metadata columns
                   (GPS columns are auto-detected by degree-sign pattern and
                   are excluded from the output)

        Point-number cleaning:
          All non-digit characters (including BOM, hyphens, letters) are
          stripped.  Names that yield no digits at all are skipped with a
          warning.

        Duplicate handling:
          • 3-D distance < threshold (default 3 mm) → same physical point
              – If the older observation has no attributes but the newer
                does, the newer row is kept (better data).
              – Otherwise the older (first) observation is kept.
          • 3-D distance ≥ threshold → both observations are valid;
              the older keeps its original number and the newer is
              automatically renumbered to the next available integer.

        Output: PENZD ASCII CSV (PointNo, Easting, Northing, Elevation,
        Description), no BOM, CRLF line endings, ready for Civil 3D import
        using import_points_from_csv with format="PENZD".

        Args:
            input_path:              Full path to the input CSV.
            output_path:             Full path for the output PENZD CSV.
            duplicate_threshold_mm:  Duplicate distance threshold in mm
                                     (default 3.0 mm).
            input_encoding:          Force encoding (e.g. "utf-8", "gbk").
                                     Auto-detected from BOM / byte patterns
                                     when omitted.
        """
        result = scsv.process_surveyor_pipeline(
            input_path=input_path,
            output_path=output_path,
            threshold_mm=duplicate_threshold_mm,
            encoding=input_encoding,
        )

        lines = [
            f"Encoding detected     : {result['encoding_detected']}",
            f"Attribute cols found  : {result['attribute_columns_detected']}",
            f"Rows input            : {result['rows_input']}",
            f"Rows output           : {result['rows_output']}",
            f"Rows discarded        : {result['rows_discarded']}",
            f"Output                : {result['output_path']}",
        ]

        if result['parse_warnings']:
            lines.append("\nParse warnings:")
            lines.extend(f"  {w}" for w in result['parse_warnings'])

        if result['duplicate_report']:
            lines.append("\nDuplicate report:")
            lines.extend(f"  {r}" for r in result['duplicate_report'])

        lines.append("\nCode summary:")
        for code, cnt in result['code_summary'].items():
            lines.append(f"  {code:14s}: {cnt}")

        lines.append(
            f"\nNext step: call import_points_from_csv with "
            f'csv_path="{result["output_path"]}", format="PENZD"'
        )

        return [TextContent(type="text", text="\n".join(lines))]

    # ── 6. Create figures using a line code file ──────────────────────────

    @app.tool()
    async def create_figures_with_code_file(
        code_file_path: str,
        site: str | None = None,
        only_tin_codes: bool = False,
    ) -> list[TextContent]:
        """
        Read a line code definition file and create feature lines / 3-D polylines
        from all COGO points already imported in the active drawing.

        The code file maps each feature code to a layer, colour, and TIN
        participation flag.  Points are grouped by their .B/.E description codes
        and drawn on the layer specified in the code file.

        Supported code file formats:
          .json — Civil 3D MCP native format (recommended)
          .csv  — positional: code, layer, color, linetype, include_in_tin

        Args:
            code_file_path: Full path to the .json or .csv code definition file.
            site:           Civil 3D site name for feature lines (optional;
                            plain 3-D polylines are used when omitted).
            only_tin_codes: When True, only codes marked include_in_tin=true
                            are drawn (useful for creating breaklines only).
        """
        lcfile = lcf.load(code_file_path)
        summary = lcfile.summary()

        codes_to_draw = (
            lcfile.tin_codes() if only_tin_codes
            else list(lcfile.codes.keys())
        )

        if not codes_to_draw:
            return [TextContent(type="text",
                text="No codes found in the code file.")]

        params: dict = {
            "layer": lcfile.default_layer,
            "code_styles": lcfile.to_code_styles(),
            "codes": codes_to_draw,
        }
        if site:
            params["site"] = site

        result = await bridge.call("create_figures", params)

        lines = [
            f"Code file         : {code_file_path}",
            f"Codes defined     : {summary['total_codes']}",
            f"Codes drawn       : {len(codes_to_draw)}",
            f"TIN breakline codes: {', '.join(summary['tin_codes'])}",
            f"Figures created   : {result}",
        ]
        return [TextContent(type="text", text="\n".join(lines))]

    # ── 7. Breakline conflict detection ───────────────────────────────────

    @app.tool()
    async def check_breakline_conflicts(
        layers: list[str] | None = None,
        tolerance_m: float = 0.001,
    ) -> list[TextContent]:
        """
        Detect crossing 3-D breaklines (Polyline3d objects) that would cause
        TIN surface artefacts in Civil 3D.

        Two breaklines conflict when their 2-D projections cross AND the
        interpolated elevations at the crossing differ by more than tolerance_m.

        Args:
            layers:      List of AutoCAD layer names to check (e.g.
                         ["C-SURV-FTRE", "C-ROAD-CNTR"]).  All 3-D polylines
                         in model space are checked when omitted.
            tolerance_m: Elevation difference below which crossing lines are
                         considered to share the same point (default 1 mm).

        Returns a list of conflicts with location (X, Y), elevation on each
        line, and the Z difference in millimetres.
        """
        params: dict = {"tolerance_m": tolerance_m}
        if layers:
            params["layers"] = layers

        result = await bridge.call("check_breakline_conflicts", params)
        n = result["total_conflicts"]

        if n == 0:
            return [TextContent(type="text", text="No breakline conflicts found.")]

        lines = [f"Found {n} breakline conflict(s):\n"]
        for i, c in enumerate(result["conflicts"], 1):
            lines.append(
                f"  {i:3d}. {c['type']:10s}  "
                f"XY=({c['x']:.3f}, {c['y']:.3f})  "
                f"Z1={c['z_line1']:.3f}  Z2={c['z_line2']:.3f}  "
                f"ΔZ={c['z_diff_mm']:.1f}mm  "
                f"lines {c['line1_handle']}/{c['line2_handle']}"
            )

        lines.append(
            f"\nCall fix_breakline_conflicts to auto-repair "
            f"(inserts shared vertices at each crossing)."
        )
        return [TextContent(type="text", text="\n".join(lines))]

    # ── 8. Breakline conflict auto-fix ────────────────────────────────────

    @app.tool()
    async def fix_breakline_conflicts(
        layers: list[str] | None = None,
        tolerance_m: float = 0.001,
        z_snap_mm: float = 10.0,
    ) -> list[TextContent]:
        """
        Automatically fix crossing 3-D breaklines so they share a vertex at
        every XY intersection, eliminating TIN surface artefacts.

        Fix strategy:
          For each crossing pair of segments, a new vertex is inserted in
          BOTH polylines at the XY intersection point.  Each polyline keeps
          its own interpolated Z (preserving survey data).  When the two Z
          values are within z_snap_mm, they are averaged to a single elevation
          (snap).

        The original polylines are replaced by new ones with the extra vertices.
        Run check_breakline_conflicts after fixing to confirm no conflicts remain.

        Args:
            layers:      Layer(s) to process (same as check_breakline_conflicts).
            tolerance_m: Minimum Z difference to count as a conflict (default 1 mm).
            z_snap_mm:   If crossing Z values are within this distance, snap them
                         to a single average elevation (default 10 mm).
        """
        params: dict = {
            "tolerance_m": tolerance_m,
            "z_snap_mm": z_snap_mm,
        }
        if layers:
            params["layers"] = layers

        result = await bridge.call("fix_breakline_conflicts", params)

        if result.get("fixed_count", 0) == 0:
            return [TextContent(type="text",
                text=result.get("message", "No conflicts to fix."))]

        lines = [
            f"Conflicts fixed   : {result['fixed_count']}",
            f"Polylines modified: {result['lines_modified']}",
            f"Vertices added    : {result['vertices_added']}",
            "",
            "All crossing breaklines now share a vertex at each intersection.",
            "The TIN surface should build without crossing-breakline warnings.",
            "Run check_breakline_conflicts again to verify.",
        ]
        return [TextContent(type="text", text="\n".join(lines))]
