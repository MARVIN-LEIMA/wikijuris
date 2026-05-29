"""HTTP client that talks to the Civil 3D .NET bridge server."""

import os
import httpx
from typing import Any

BRIDGE_URL = os.environ.get("CIVIL3D_BRIDGE_URL", "http://localhost:3765")
TIMEOUT = float(os.environ.get("CIVIL3D_BRIDGE_TIMEOUT", "30"))


async def call(tool: str, params: dict[str, Any]) -> Any:
    """Send a tool call to the Civil 3D bridge and return the result dict."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{BRIDGE_URL}/api/execute",
            json={"tool": tool, "params": params},
        )
    data = response.json()
    if not response.is_success or not data.get("ok"):
        raise RuntimeError(data.get("error", f"HTTP {response.status_code}"))
    return data.get("result")
