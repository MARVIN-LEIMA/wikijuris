"""MCP tools for Civil 3D pipe network operations."""

from mcp.server import Server
from mcp.types import TextContent
from .. import bridge_client as bridge


def register(app: Server) -> None:

    @app.tool()
    async def create_pipe_network(
        name: str,
        description: str = "",
        alignment: str | None = None,
    ) -> list[TextContent]:
        """Create a new Civil 3D pipe network.

        Args:
            name: Unique network name.
            description: Optional description.
            alignment: Name of a reference alignment (optional).
        """
        result = await bridge.call("create_pipe_network", {
            "name": name, "description": description,
            **({"alignment": alignment} if alignment else {}),
        })
        return [TextContent(type="text", text=f"Pipe network created: {result}")]

    @app.tool()
    async def add_structure(
        network: str,
        x: float,
        y: float,
        rim_elevation: float | None = None,
        sump_elevation: float | None = None,
        part_family: str = "Concrete Rectangular Structure",
        part_size: str = "30x48 Box",
        rotation: float = 0,
    ) -> list[TextContent]:
        """Add a structure (manhole, catch basin, junction) to a pipe network.

        Returns the structure handle which can be used to connect pipes.

        Args:
            network: Name of the target pipe network.
            x/y: Plan location of the structure.
            rim_elevation: Top (rim) elevation; None = auto.
            sump_elevation: Bottom (sump) elevation; None = auto.
            part_family: Civil 3D part catalog family name.
            part_size: Part size name within the family.
            rotation: Rotation angle in degrees.
        """
        params: dict = {
            "network": network, "x": x, "y": y,
            "part_family": part_family, "part_size": part_size,
            "rotation": rotation,
        }
        if rim_elevation is not None:
            params["rim_elevation"] = rim_elevation
        if sump_elevation is not None:
            params["sump_elevation"] = sump_elevation

        result = await bridge.call("add_structure", params)
        return [TextContent(type="text", text=f"Structure added: {result}")]

    @app.tool()
    async def add_pipe(
        network: str,
        start: list[float],
        end: list[float],
        part_family: str = "Concrete Pipe",
        part_size: str = "12 inch Concrete Pipe",
        start_structure: str | None = None,
        end_structure: str | None = None,
    ) -> list[TextContent]:
        """Add a pipe segment to a pipe network.

        Args:
            network: Name of the target pipe network.
            start: [x, y, z] start point (invert elevation).
            end: [x, y, z] end point (invert elevation).
            part_family: Civil 3D part catalog family name.
            part_size: Part size name within the family.
            start_structure: Handle of the structure at the start end (optional).
            end_structure: Handle of the structure at the end end (optional).
        """
        params: dict = {
            "network": network,
            "start": start,
            "end": end,
            "part_family": part_family,
            "part_size": part_size,
        }
        if start_structure:
            params["start_structure"] = start_structure
        if end_structure:
            params["end_structure"] = end_structure

        result = await bridge.call("add_pipe", params)
        return [TextContent(type="text", text=f"Pipe added: {result}")]

    @app.tool()
    async def set_pipe_slope(
        pipe: str,
        slope: float,
    ) -> list[TextContent]:
        """Set the slope (rise/run) of an existing pipe segment.

        Args:
            pipe: Handle of the pipe object (returned by add_pipe).
            slope: Slope as a decimal fraction, e.g. 0.005 = 0.5%.
        """
        result = await bridge.call("set_pipe_slope", {
            "pipe": pipe, "slope": slope
        })
        return [TextContent(type="text", text=f"Slope set: {result}")]
