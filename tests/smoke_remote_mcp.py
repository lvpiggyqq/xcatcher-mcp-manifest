#!/usr/bin/env python3
"""No-auth, no-side-effect contract smoke test for Xcatcher Remote MCP."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


MCP_URL = os.environ.get("XCATCHER_MCP_URL", "https://xcatcher.top/mcp/")


def rpc(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    ).encode("utf-8")
    request = urllib.request.Request(
        MCP_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "xcatcher-public-smoke/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")

    if "text/event-stream" in content_type:
        data_lines = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
        if not data_lines:
            raise AssertionError("MCP returned an empty event stream")
        body = data_lines[-1]

    result = json.loads(body)
    if result.get("error"):
        raise AssertionError(f"MCP error: {result['error']}")
    return result


def tool_result(response: dict[str, Any]) -> dict[str, Any]:
    result = response["result"]
    if result.get("isError"):
        raise AssertionError(f"Tool returned isError: {result}")
    structured = result.get("structuredContent", {}).get("result")
    if not isinstance(structured, dict):
        raise AssertionError("Tool did not return structuredContent.result")
    return structured


def main() -> None:
    listed = rpc(1, "tools/list", {})
    tools = listed["result"]["tools"]
    names = {tool["name"] for tool in tools}
    required = {"get_service_info", "preflight_crawl", "get_sample_result"}
    assert len(tools) >= 17, f"Expected at least 17 tools, got {len(tools)}"
    assert required <= names, f"Missing tools: {sorted(required - names)}"
    assert all(tool.get("description") for tool in tools), "A tool description is empty"

    preflight = tool_result(
        rpc(
            2,
            "tools/call",
            {
                "name": "preflight_crawl",
                "arguments": {
                    "users": ["@OpenAI", "https://x.com/naval", "OpenAI"],
                    "mode": "normal",
                },
            },
        )
    )
    assert preflight.get("ok") is True
    assert preflight["normalized_request"]["users"] == ["OpenAI", "naval"]
    assert preflight["estimate"]["cost_points"] == 2
    assert preflight["effects"] == {
        "authentication_required": False,
        "creates_quote": False,
        "creates_task": False,
        "moves_funds": False,
    }

    sample = tool_result(
        rpc(3, "tools/call", {"name": "get_sample_result", "arguments": {}})
    )
    assert sample.get("ok") is True
    assert sample.get("data_origin") == "synthetic_example"
    assert sample.get("rows"), "Synthetic sample has no rows"
    assert sample["effects"]["moves_funds"] is False

    print(f"PASS: {len(tools)} tools; free preflight and synthetic sample are healthy")


if __name__ == "__main__":
    main()
