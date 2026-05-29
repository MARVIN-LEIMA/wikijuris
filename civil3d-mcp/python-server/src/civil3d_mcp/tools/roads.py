"""MCP tools for Civil 3D alignment, profile, and corridor operations."""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    # ── Alignments ─────────────────────────────────────────────────────────

    @app.tool()
    async def create_alignment(
        name: str,
        description: str = "",
        layer: str = "C-ROAD-CNTR",
        site: str | None = None,
    ) -> list[TextContent]:
        """Create a new horizontal alignment (road centre line).

        After creating, add geometry with add_alignment_tangent / add_alignment_curve.

        Args:
            name: Unique alignment name.
            description: Optional description.
            layer: AutoCAD layer.
            site: Site name (optional — alignments can be siteless in Civil 3D 2020+).
        """
        params: dict = {"name": name, "description": description, "layer": layer}
        if site:
            params["site"] = site
        result = await bridge.call("create_alignment", params)
        return [TextContent(type="text", text=f"Alignment created: {result}")]

    @app.tool()
    async def add_alignment_tangent(
        alignment: str,
        start: list[float],
        end: list[float],
    ) -> list[TextContent]:
        """Append a fixed tangent (straight) segment to an alignment.

        Args:
            alignment: Name of the target alignment.
            start: [x, y] start point.
            end: [x, y] end point.
        """
        result = await bridge.call("add_alignment_tangent", {
            "alignment": alignment, "start": start, "end": end
        })
        return [TextContent(type="text", text=f"Tangent added: {result}")]

    @app.tool()
    async def add_alignment_curve(
        alignment: str,
        radius: float,
        pass_through: list[float],
    ) -> list[TextContent]:
        """Append a horizontal curve to the end of an alignment.

        The curve is inserted as a free arc that connects the last two alignment
        entities with the given radius passing through the specified point.

        Args:
            alignment: Name of the target alignment.
            radius: Curve radius in drawing units.
            pass_through: [x, y] point the curve should pass through.
        """
        result = await bridge.call("add_alignment_curve", {
            "alignment": alignment, "radius": radius, "pass_through": pass_through
        })
        return [TextContent(type="text", text=f"Curve added: {result}")]

    # ── Profiles ───────────────────────────────────────────────────────────

    @app.tool()
    async def create_profile_view(
        alignment: str,
        origin_x: float,
        origin_y: float,
        name: str | None = None,
    ) -> list[TextContent]:
        """Create a profile view sheet for an alignment.

        The profile view is placed at the given drawing coordinates.

        Args:
            alignment: Name of the alignment.
            origin_x/y: Bottom-left insertion point in model space.
            name: Optional profile view name (auto-generated if omitted).
        """
        params: dict = {
            "alignment": alignment,
            "origin": [origin_x, origin_y],
        }
        if name:
            params["name"] = name
        result = await bridge.call("create_profile_view", params)
        return [TextContent(type="text", text=f"Profile view created: {result}")]

    @app.tool()
    async def create_layout_profile(
        alignment: str,
        name: str,
        description: str = "",
    ) -> list[TextContent]:
        """Create an empty layout (design) profile attached to an alignment.

        Add PVIs to define the vertical geometry with add_profile_pvi.

        Args:
            alignment: Name of the alignment.
            name: Unique profile name.
            description: Optional description.
        """
        result = await bridge.call("create_layout_profile", {
            "alignment": alignment, "name": name, "description": description
        })
        return [TextContent(type="text", text=f"Layout profile created: {result}")]

    @app.tool()
    async def add_profile_pvi(
        alignment: str,
        profile: str,
        station: float,
        elevation: float,
        curve_length: float | None = None,
    ) -> list[TextContent]:
        """Add a PVI (Point of Vertical Intersection) to a layout profile.

        A vertical parabolic curve is attached when curve_length is specified.

        Args:
            alignment: Name of the parent alignment.
            profile: Name of the layout profile.
            station: Station value along the alignment.
            elevation: Elevation at the PVI.
            curve_length: Length of the vertical parabola (optional).
        """
        params: dict = {
            "alignment": alignment,
            "profile": profile,
            "station": station,
            "elevation": elevation,
        }
        if curve_length is not None:
            params["curve_length"] = curve_length
        result = await bridge.call("add_profile_pvi", params)
        return [TextContent(type="text", text=f"PVI added: {result}")]

    # ── Assembly & Corridor ────────────────────────────────────────────────

    @app.tool()
    async def create_assembly(
        name: str,
        x: float = 0,
        y: float = 0,
    ) -> list[TextContent]:
        """Create a road cross-section assembly.

        Subassemblies (lanes, curbs, sidewalks) can be applied manually in
        Civil 3D after the assembly is created; then attach it to a corridor
        via create_corridor.

        Args:
            name: Unique assembly name.
            x/y: Placement location in model space (can be anywhere off-road).
        """
        result = await bridge.call("create_assembly", {
            "name": name, "x": x, "y": y
        })
        return [TextContent(type="text", text=f"Assembly created: {result}")]

    @app.tool()
    async def create_corridor(
        name: str,
        alignment: str,
        profile: str,
        assembly: str,
        target_surface: str | None = None,
    ) -> list[TextContent]:
        """Create a road corridor from an alignment, profile, and assembly.

        Args:
            name: Unique corridor name.
            alignment: Name of the horizontal alignment.
            profile: Name of the design profile attached to the alignment.
            assembly: Name of the road cross-section assembly.
            target_surface: Name of an existing TIN surface for daylight targeting
                (optional).
        """
        params: dict = {
            "name": name,
            "alignment": alignment,
            "profile": profile,
            "assembly": assembly,
        }
        if target_surface:
            params["target_surface"] = target_surface
        result = await bridge.call("create_corridor", params)
        return [TextContent(type="text", text=f"Corridor created: {result}")]
