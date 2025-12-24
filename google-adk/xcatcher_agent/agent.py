import os

from google.adk.agents import Agent

# ADK import compat
try:
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
except Exception:
    from google.adk.tools.mcp_tool import MCPToolset as McpToolset  # type: ignore
    from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams  # type: ignore


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


XCAT_BASE = _env("XCAT_BASE", "https://xcatcher.top").rstrip("/")
XCAT_API_KEY = _env("XCAT_API_KEY", "")

if not XCAT_API_KEY:
    print("WARNING: missing XCAT_API_KEY env var (xc_live_...). Tool calls will fail.")

toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=f"{XCAT_BASE}/mcp",
        headers={
            "Authorization": f"Bearer {XCAT_API_KEY}",
            "Accept": "application/json",
        },
    ),
    tool_filter=[
        "create_crawl_task",
        "x402_topup",
        "get_task_status",
        "get_result_download_url",
        "cancel_task",
    ],
)

agent = Agent(
    name="xcatcher_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are an agent that uses Xcatcher Remote MCP to create crawl tasks for X (Twitter) users.\n"
        "\n"
        "Defaults:\n"
        "- Prefer mode=normal because it is faster.\n"
        "\n"
        "Rules:\n"
        "- MCP calls MUST include Accept: application/json (already set).\n"
        "- create_crawl_task consumes points (side effect). Always include a stable idempotency_key.\n"
        "- If you receive ok=false with error.code=PAYMENT_REQUIRED:\n"
        "  1) Explain that payTo/amount are returned dynamically by the quote, so txHash/signature cannot be known in advance.\n"
        "  2) Ask the user to pay USDC to the returned payTo address.\n"
        "  3) Minimum top-up is 0.50 USDC (Base/Solana). Ask the user to send at least 0.50 USDC.\n"
        "  4) After payment, ask for Base txHash or Solana signature.\n"
        "  5) Call x402_topup, then retry create_crawl_task with the SAME idempotency_key.\n"
        "- Poll get_task_status until has_result=true.\n"
        "- get_result_download_url returns a URL; downloading still requires the same Bearer token.\n"
    ),
    tools=[toolset],
)
