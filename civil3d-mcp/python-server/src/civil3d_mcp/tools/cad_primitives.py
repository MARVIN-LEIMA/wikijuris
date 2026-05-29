"""MCP tools for basic AutoCAD drawing primitives."""

from mcp.server import Server
from mcp.types import Tool, TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    @app.tool()
    async def create_layer(name: str, color: int = 7, linetype: str = "Continuous") -> list[TextContent]:
        """Create a new CAD layer.

        Args:
            name: Layer name (e.g. "C-ROAD-CNTR").
            color: AutoCAD color index 1-256 (default 7 = white).
            linetype: Linetype name (default "Continuous").
        """
        result = await bridge.call("create_layer", {
            "name": name, "color": color, "linetype": linetype
        })
        return [TextContent(type="text", text=f"Layer created: {result}")]

    @app.tool()
    async def draw_point(x: float, y: float, z: float = 0, layer: str = "0") -> list[TextContent]:
        """Draw a single point in model space.

        Args:
            x: X coordinate.
            y: Y coordinate.
            z: Z (elevation) coordinate, default 0.
            layer: Target layer name.
        """
        result = await bridge.call("draw_point", {
            "point": [x, y, z], "layer": layer
        })
        return [TextContent(type="text", text=f"Point drawn: {result}")]

    @app.tool()
    async def draw_line(
        start_x: float, start_y: float, start_z: float,
        end_x: float, end_y: float, end_z: float,
        layer: str = "0"
    ) -> list[TextContent]:
        """Draw a straight line between two 3D points.

        Args:
            start_x/y/z: Start point coordinates.
            end_x/y/z: End point coordinates.
            layer: Target layer name.
        """
        result = await bridge.call("draw_line", {
            "start": [start_x, start_y, start_z],
            "end": [end_x, end_y, end_z],
            "layer": layer,
        })
        return [TextContent(type="text", text=f"Line drawn: {result}")]

    @app.tool()
    async def draw_polyline(
        points: list[list[float]],
        layer: str = "0",
        closed: bool = False,
        elevation: float = 0,
    ) -> list[TextContent]:
        """Draw a 2D polyline from a list of [x, y] or [x, y, z] coordinate pairs.

        Args:
            points: List of [x, y] or [x, y, z] coordinate pairs.
            layer: Target layer name.
            closed: Whether to close the polyline back to the first vertex.
            elevation: Constant Z elevation for the polyline.
        """
        result = await bridge.call("draw_polyline", {
            "points": points, "layer": layer, "closed": closed, "elevation": elevation
        })
        return [TextContent(type="text", text=f"Polyline drawn: {result}")]

    @app.tool()
    async def draw_arc(
        center_x: float, center_y: float, center_z: float = 0,
        radius: float = 1.0,
        start_angle: float = 0, end_angle: float = 180,
        layer: str = "0",
    ) -> list[TextContent]:
        """Draw a circular arc.

        Args:
            center_x/y/z: Center of the arc.
            radius: Arc radius.
            start_angle: Start angle in degrees (0 = east, CCW positive).
            end_angle: End angle in degrees.
            layer: Target layer name.
        """
        result = await bridge.call("draw_arc", {
            "center": [center_x, center_y, center_z],
            "radius": radius,
            "start_angle": start_angle,
            "end_angle": end_angle,
            "layer": layer,
        })
        return [TextContent(type="text", text=f"Arc drawn: {result}")]

    @app.tool()
    async def draw_circle(
        center_x: float, center_y: float, center_z: float = 0,
        radius: float = 1.0,
        layer: str = "0",
    ) -> list[TextContent]:
        """Draw a circle.

        Args:
            center_x/y/z: Center point.
            radius: Circle radius.
            layer: Target layer name.
        """
        result = await bridge.call("draw_circle", {
            "center": [center_x, center_y, center_z],
            "radius": radius,
            "layer": layer,
        })
        return [TextContent(type="text", text=f"Circle drawn: {result}")]

    @app.tool()
    async def draw_text(
        text: str,
        position_x: float, position_y: float, position_z: float = 0,
        height: float = 2.5,
        rotation: float = 0,
        layer: str = "0",
    ) -> list[TextContent]:
        """Add a multiline text annotation to the drawing.

        Args:
            text: The text string (supports MText formatting codes).
            position_x/y/z: Insertion point.
            height: Text height in drawing units.
            rotation: Rotation angle in degrees.
            layer: Target layer name.
        """
        result = await bridge.call("draw_text", {
            "text": text,
            "position": [position_x, position_y, position_z],
            "height": height,
            "rotation": rotation,
            "layer": layer,
        })
        return [TextContent(type="text", text=f"Text placed: {result}")]
