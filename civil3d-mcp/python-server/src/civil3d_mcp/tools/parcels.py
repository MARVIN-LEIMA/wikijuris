"""MCP tools for Civil 3D parcel / land division operations."""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    @app.tool()
    async def create_parcel_site(
        name: str,
        description: str = "",
    ) -> list[TextContent]:
        """Create a new Civil 3D site that will contain parcels.

        Args:
            name: Unique site name.
            description: Optional description.
        """
        result = await bridge.call("create_parcel_site", {
            "name": name, "description": description
        })
        return [TextContent(type="text", text=f"Site created: {result}")]

    @app.tool()
    async def create_parcel_from_polyline(
        site: str,
        points: list[list[float]],
        layer: str = "C-PROP",
    ) -> list[TextContent]:
        """Create a land parcel from a closed polygon defined by XY vertices.

        The vertices define the boundary; the polygon is automatically closed.

        Args:
            site: Name of the site to add the parcel to.
            points: List of [x, y] boundary vertices.
            layer: AutoCAD layer for the boundary polyline.
        """
        result = await bridge.call("create_parcel_from_polyline", {
            "site": site, "points": points, "layer": layer
        })
        return [TextContent(type="text", text=f"Parcel created: {result}")]

    @app.tool()
    async def subdivide_parcel(
        site: str,
        segment_lines: list[list[list[float]]],
        layer: str = "C-PROP",
    ) -> list[TextContent]:
        """Subdivide existing parcels by adding segment lines into a site.

        Each segment line splits the parcel it crosses. Civil 3D automatically
        recomputes parcel boundaries.

        Args:
            site: Name of the site containing the parcels to subdivide.
            segment_lines: List of line segments; each is [[x1,y1],[x2,y2]].
            layer: AutoCAD layer for the segment lines.
        """
        result = await bridge.call("subdivide_parcel", {
            "site": site, "segment_lines": segment_lines, "layer": layer
        })
        return [TextContent(type="text", text=f"Parcel subdivided: {result}")]
