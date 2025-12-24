#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys

try:
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
except Exception:
    # Older ADK naming fallback
    from google.adk.tools.mcp_tool import MCPToolset as McpToolset  # type: ignore
    from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams  # type: ignore


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


async def _maybe_await(x):
    return await x if asyncio.iscoroutine(x) else x


async def _close_toolset(toolset) -> None:
    for m in ("aclose", "close"):
        if hasattr(toolset, m):
            try:
                await _maybe_await(getattr(toolset, m)())
            except Exception:
                pass
            return


async def main() -> int:
    base = _env("XCAT_BASE", "https://xcatcher.top").rstrip("/")
    api_key = _env("XCAT_API_KEY", "")
    if not api_key:
        print("ERROR: missing env XCAT_API_KEY", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=f"{base}/mcp",
            headers=headers,
        )
    )

    try:
        if hasattr(toolset, "get_tools_async"):
            tools = await _maybe_await(toolset.get_tools_async())
        elif hasattr(toolset, "get_tools"):
            tools = await _maybe_await(toolset.get_tools())
        else:
            tools = await _maybe_await(getattr(toolset, "tools"))

        print("Available MCP tools:")
        for t in tools:
            name = getattr(t, "name", None) or getattr(t, "tool_name", None) or str(t)
            print(f" - {name}")
        return 0
    finally:
        await _close_toolset(toolset)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
