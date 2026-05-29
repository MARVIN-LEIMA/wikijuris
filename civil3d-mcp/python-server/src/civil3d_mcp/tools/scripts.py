"""
MCP tools to run external Python / Node.js / shell scripts.

The MCP server runs on the same machine as Civil 3D, so these tools
give AI agents a way to execute arbitrary data-transformation scripts
before piping the results into Civil 3D.
"""

import shutil
import sys
from mcp.server import Server
from mcp.types import TextContent
from .. import csv_utils


def register(app: Server) -> None:

    @app.tool()
    async def run_python_script(
        script_path: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        timeout: int = 60,
    ) -> list[TextContent]:
        """
        Execute a Python script file and capture its output.

        The script runs with the same Python interpreter that hosts this MCP
        server, so any packages installed in that environment are available.

        Args:
            script_path: Full path to the .py file.
            args:        Command-line arguments passed after the script path.
            cwd:         Working directory (defaults to the script's directory).
            timeout:     Maximum runtime in seconds (default 60).
        """
        cmd = [sys.executable, script_path, *(args or [])]
        result = csv_utils.run_external(cmd, cwd=cwd, timeout=timeout)
        return [TextContent(type="text", text=_fmt(result))]

    @app.tool()
    async def run_node_script(
        script_path: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        timeout: int = 60,
    ) -> list[TextContent]:
        """
        Execute a Node.js / JavaScript script file and capture its output.

        Node.js must be installed and on the system PATH.

        Args:
            script_path: Full path to the .js file.
            args:        Command-line arguments passed after the script path.
            cwd:         Working directory (defaults to the script's directory).
            timeout:     Maximum runtime in seconds (default 60).
        """
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            return [TextContent(type="text",
                                text="Error: Node.js not found on PATH.")]
        cmd = [node, script_path, *(args or [])]
        result = csv_utils.run_external(cmd, cwd=cwd, timeout=timeout)
        return [TextContent(type="text", text=_fmt(result))]

    @app.tool()
    async def run_shell_command(
        command: str,
        cwd: str | None = None,
        timeout: int = 30,
    ) -> list[TextContent]:
        """
        Run an arbitrary shell command (cmd.exe on Windows, sh on Linux/Mac).

        Use with care — the command runs with the permissions of the MCP
        server process.

        Args:
            command: Shell command string, e.g. "dir C:\\Data" or "ls -la /data".
            cwd:     Working directory.
            timeout: Maximum runtime in seconds (default 30).
        """
        import platform
        if platform.system() == "Windows":
            cmd = ["cmd.exe", "/C", command]
        else:
            cmd = ["/bin/sh", "-c", command]
        result = csv_utils.run_external(cmd, cwd=cwd, timeout=timeout)
        return [TextContent(type="text", text=_fmt(result))]


def _fmt(r: dict) -> str:
    parts = [f"Exit code: {r['returncode']}"]
    if r.get("stdout"):
        parts.append(f"--- stdout ---\n{r['stdout']}")
    if r.get("stderr"):
        parts.append(f"--- stderr ---\n{r['stderr']}")
    return "\n".join(parts)
