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
