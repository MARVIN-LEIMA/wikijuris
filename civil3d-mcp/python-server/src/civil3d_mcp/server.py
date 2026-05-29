"""Civil 3D MCP server entry point."""

import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from . import tools as t


def build_server() -> Server:
    app = Server("civil3d-mcp")
    t.register_cad(app)
    t.register_surfaces(app)
    t.register_parcels(app)
    t.register_pipes(app)
    t.register_roads(app)
    t.register_points(app)
    t.register_scripts(app)
    t.register_drawing(app)
    return app


def main() -> None:
    app = build_server()
    asyncio.run(_run(app))


async def _run(app: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    main()
