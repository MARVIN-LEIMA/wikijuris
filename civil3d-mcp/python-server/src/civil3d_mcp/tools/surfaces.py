"""MCP tools for Civil 3D TIN surface operations."""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    @app.tool()
    async def create_tin_surface(
        name: str,
        description: str = "",
        layer: str = "C-TOPO",
    ) -> list[TextContent]:
        """Create a new empty TIN surface in the current drawing.

        Args:
            name: Unique surface name.
            description: Optional description.
            layer: AutoCAD layer for the surface object.
        """
        result = await bridge.call("create_tin_surface", {
            "name": name, "description": description, "layer": layer
        })
        return [TextContent(type="text", text=f"TIN surface created: {result}")]

    @app.tool()
    async def add_surface_points(
        surface: str,
        points: list[list[float]],
    ) -> list[TextContent]:
        """Add elevation (XYZ) points to a TIN surface.

        Args:
            surface: Name of the target surface.
            points: List of [x, y, z] elevation points.
        """
        result = await bridge.call("add_surface_points", {
            "surface": surface, "points": points
        })
        return [TextContent(type="text", text=f"Points added: {result}")]

    @app.tool()
    async def add_surface_breaklines(
        surface: str,
        lines: list[list[list[float]]],
        type: str = "standard",
        description: str = "Breaklines",
    ) -> list[TextContent]:
        """Add breaklines to a TIN surface to enforce edges along linear features.

        Args:
            surface: Name of the target surface.
            lines: List of breakline segments; each segment is a list of [x, y, z] points.
            type: "standard" (default) or "proximity".
            description: Label for the breakline group.
        """
        result = await bridge.call("add_surface_breaklines", {
            "surface": surface, "lines": lines, "type": type,
            "description": description
        })
        return [TextContent(type="text", text=f"Breaklines added: {result}")]

    @app.tool()
    async def add_surface_boundary(
        surface: str,
        points: list[list[float]],
        type: str = "outer",
    ) -> list[TextContent]:
        """Add a boundary polygon to a TIN surface.

        Args:
            surface: Name of the target surface.
            points: List of [x, y] points defining the boundary polygon (auto-closed).
            type: "outer" (default), "hide", "show", or "data".
        """
        result = await bridge.call("add_surface_boundary", {
            "surface": surface, "points": points, "type": type
        })
        return [TextContent(type="text", text=f"Boundary added: {result}")]

    @app.tool()
    async def build_surface(surface: str) -> list[TextContent]:
        """Rebuild / recompute a TIN surface after adding data.

        Args:
            surface: Name of the surface to rebuild.
        """
        result = await bridge.call("build_surface", {"surface": surface})
        return [TextContent(type="text", text=f"Surface rebuilt: {result}")]

    @app.tool()
    async def get_surface_elevation(
        surface: str, x: float, y: float
    ) -> list[TextContent]:
        """Query the interpolated elevation of a surface at a specific XY location.

        Args:
            surface: Name of the surface.
            x: X coordinate.
            y: Y coordinate.
        """
        result = await bridge.call("get_surface_elevation", {
            "surface": surface, "x": x, "y": y
        })
        return [TextContent(type="text", text=f"Elevation at ({x}, {y}): {result}")]
