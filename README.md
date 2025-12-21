# Xcatcher MCP (Remote)

Xcatcher is a **Remote MCP server** (Streamable HTTP) and a **REST API** for high-throughput crawling of **fresh / latest posts** across large sets of X (Twitter) usernames, with **authenticated XLSX export**.

## Endpoints

- Base URL: https://xcatcher.top
- Remote MCP (Streamable HTTP): https://xcatcher.top/mcp
- REST API: https://xcatcher.top/api/v1
- Docs: https://xcatcher.top/docs/
- Health: https://xcatcher.top/mcp/health

## Authentication

All MCP and REST calls require:

- `Authorization: Bearer xc_live_...`

Important: Result files are not public direct links. Always download via authenticated endpoints using the same Bearer token.

---

## Modes: `normal` vs `deep`

Choose the mode based on your goal:

### `normal` (recommended for monitoring / fresh feed)
- Purpose: **fast “latest posts” snapshot** across many users
- Best for: high-concurrency monitoring, alerting, pipelines that repeatedly fetch new posts
- Typical: fastest turnaround and highest throughput

### `deep`
- Purpose: **deeper per-user collection / enrichment**
- Best for: deeper historical/contextual pulls where latency is less critical
- Typical: slower than normal and uses more resources

Notes:
- Exact cost and remaining balance are returned by the server (e.g., `cost_points`, `balance_after`) when you create a task.

---

## High-throughput / concurrency (what Xcatcher is optimized for)

Xcatcher is designed for batch “fresh content” retrieval.

Typical benchmark (Normal mode):
- ~1000 X users → ~5000 tweets in ~2 minutes under normal conditions.

Disclaimers:
- Actual throughput depends on the time window, X platform rate limits, and network conditions.
- For very large sets, split into multiple tasks (batching) and run concurrently if your quota allows.

Recommended workflow:
1) create task
2) poll status
3) download result

---

## Remote MCP tools (high level)

Xcatcher exposes a small agent-friendly core:

- `create_crawl_task`: create a crawl task (side effect: consumes points)
- `get_task_status`: poll until done
- `get_result_download_url`: get the authenticated XLSX download URL
- `cancel_task`: cancel a queued task (if supported)

Agents should rely on the tool schema (`tools/list`) for exact input fields and constraints.

---

## Quickstart (Google ADK → Remote MCP)

```python
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

toolset = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://xcatcher.top/mcp",
        headers={"Authorization": "Bearer xc_live_xxx"},
    ),
    tool_filter=[
        "create_crawl_task",
        "get_task_status",
        "get_result_download_url",
        "cancel_task",
    ],
)
Recommended agent flow:

create_crawl_task with mode and users (+ idempotency_key recommended)

poll get_task_status every 5–10 seconds

get_result_download_url, then download using the same Bearer token

Quickstart (REST API)
bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

# Verify token / connectivity
curl -s "$BASE/api/v1/me" \
  -H "Authorization: Bearer $API_KEY"

# Create task (side-effect: consumes points)
curl -s -X POST "$BASE/api/v1/tasks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"normal","users":["elonmusk","naval"],"idempotency_key":"YOUR_IDEMPOTENCY_KEY"}'

# Poll status
TASK_ID=10136
curl -s "$BASE/api/v1/tasks/$TASK_ID" \
  -H "Authorization: Bearer $API_KEY"

# Download XLSX (stream)
curl -L -o result.xlsx \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE/api/v1/tasks/$TASK_ID/download"
Polling guidance:

Poll every 5–10 seconds under normal conditions.

If you receive 429, back off and honor Retry-After.

Idempotency:

Always pass idempotency_key for create calls to prevent double charges during retries.

Payment / Top-up (two options)
Create a top-up order:

POST /mcp/payment/create
Then poll:

GET /mcp/payment/status/<payment_id>

Option A: ETH transfer on Ethereum
bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

curl -s -X POST "$BASE/mcp/payment/create" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount_usd":20,"pay_currency":"eth"}'

PAYMENT_ID="YOUR_PAYMENT_ID"
curl -s "$BASE/mcp/payment/status/$PAYMENT_ID" \
  -H "Authorization: Bearer $API_KEY"
Option B: USDT transfer on Solana (SPL)
Use pay_currency: "usdtsol" (USDT on Solana). 
NOWPayments
+1

bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

curl -s -X POST "$BASE/mcp/payment/create" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount_usd":20,"pay_currency":"usdtsol"}'

PAYMENT_ID="YOUR_PAYMENT_ID"
curl -s "$BASE/mcp/payment/status/$PAYMENT_ID" \
  -H "Authorization: Bearer $API_KEY"
Payment safety notes:

Always send the exact amount returned by the API to the returned address.

Ensure you send on the correct network (Ethereum vs Solana SPL). Sending on the wrong network may fail or require manual recovery.

Error handling (agent branching)
401 AUTH_MISSING / AUTH_INVALID: missing/invalid Bearer token

409 RESULT_NOT_READY: keep polling

429 RATE_LIMITED: back off, honor Retry-After

5xx: transient errors; retry with backoff

Support
Docs: https://xcatcher.top/docs/

Issues / requests: open an issue in this repository.
