"""
MCP tools for drawing-lifecycle management:
  new_drawing        — create a DWG from a Civil 3D template
  save_drawing       — save (or save-as) the active drawing
  get_drawing_info   — query path / modified state
"""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    @app.tool()
    async def new_drawing(
        template_path: str,
        output_path: str,
    ) -> list[TextContent]:
        """
        Create a new Civil 3D drawing from a template file (.dwt or .dwg)
        and save it to the specified output path.

        The new drawing becomes the active document immediately, so all
        subsequent tool calls (import_points, create_figures …) operate
        on it.

        Args:
            template_path: Full path to the .dwt / .dwg template.
                           E.g. "C:/Templates/CivilMetric.dwt"
            output_path:   Full path for the new .dwg file.
                           Parent directories are created automatically.
        """
        result = await bridge.call("new_drawing_from_template", {
            "template_path": template_path,
            "output_path": output_path,
        })
        return [TextContent(type="text",
            text=f"New drawing created from template '{result['template']}': "
                 f"{result['output_path']}")]

    @app.tool()
    async def save_drawing(path: str | None = None) -> list[TextContent]:
        """
        Save the active Civil 3D drawing.

        Args:
            path: Optional new file path for Save As.  Omit to save in place.
        """
        params = {}
        if path:
            params["path"] = path
        result = await bridge.call("save_drawing", params)
        return [TextContent(type="text", text=f"Drawing saved: {result['saved_path']}")]

    @app.tool()
    async def get_drawing_info() -> list[TextContent]:
        """
        Return the path and modified state of the active drawing.
        Useful for confirming which file subsequent operations will write to.
        """
        result = await bridge.call("get_drawing_info", {})
        modified = "modified" if result["modified"] else "saved"
        return [TextContent(type="text",
            text=f"Active drawing ({modified}): {result['path']}")]
