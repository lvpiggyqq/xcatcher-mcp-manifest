````markdown
# Xcatcher MCP (Remote)

Xcatcher provides a Remote MCP server and a REST API for crawling X (Twitter) targets, polling task progress, and exporting results as authenticated downloads.

## Endpoints

- Base URL: https://xcatcher.top
- Remote MCP (Streamable HTTP): https://xcatcher.top/mcp
- REST API: https://xcatcher.top/api/v1
- Health: https://xcatcher.top/mcp/health
- Docs: https://xcatcher.top/docs/

Authentication (both MCP + REST):

- Authorization: Bearer xc_live_...

Important: Result files are not exposed as public direct links. Always download via authenticated endpoints using the same Bearer token.

## What this MCP server is for (high-level)

Remote MCP tools are intentionally focused on a small “agent-friendly” core:

- create_crawl_task: create a crawl task (side-effect: consumes points). Supports mode and optional idempotency_key.
- get_task_status: return task status (poll until done).
- get_result_download_url: return an absolute download_url for the XLSX result (Bearer still required).
- cancel_task: cancel a queued task (subject to backend policy).

## Quickstart (Remote MCP)

### Google ADK example

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
````

### Recommended agent workflow

1. Call create_crawl_task with:

   * mode: "normal" or "deep"
   * users: array of X usernames (strings)
   * idempotency_key: recommended for retry-safe execution

2. Poll get_task_status every 5–10 seconds until completed.

3. Call get_result_download_url and download with the same Bearer token.

## Quickstart (REST API)

Typical flow: obtain an API key, verify it, create a task, poll status, download the XLSX result.

```bash
# 0) Base + key placeholder
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

# 1) (Optional) Register → returns api_key
curl -s -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

# 2) Login → issues a new api_key (old key may be revoked)
curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

# 3) Verify token / connectivity
curl -s "$BASE/api/v1/me" \
  -H "Authorization: Bearer $API_KEY"

# 4) Create task (side-effect: consumes points)
#    mode: "normal" | "deep"
#    users: array of X usernames (strings)
#    idempotency_key: optional but recommended
curl -s -X POST "$BASE/api/v1/tasks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"normal","users":["elonmusk","naval"],"idempotency_key":"YOUR_IDEMPOTENCY_KEY"}'

# 5) Poll status until done
TASK_ID=10136
curl -s "$BASE/api/v1/tasks/$TASK_ID" \
  -H "Authorization: Bearer $API_KEY"

# 6) Download result (XLSX stream, not JSON)
curl -L -o result.xlsx \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE/api/v1/tasks/$TASK_ID/download"
```

Notes:

* idempotency_key is recommended for clients/agents that may retry requests.
* On success, task creation may return fields like cost_points and balance_after.

## Polling & idempotency guidance

* Poll get_task_status every 5–10 seconds under normal conditions.
* If you receive 429, back off and honor Retry-After (if present).
* Always use idempotency_key for create calls to prevent double charges during retries.

## Error codes (agent branching)

* 401 AUTH_MISSING / AUTH_INVALID:
  Missing Bearer header, or token invalid/expired/blank/contaminated.
* 409 RESULT_NOT_READY:
  Task is not completed yet; keep polling.
* 429 RATE_LIMITED:
  Rate limit exceeded; honor Retry-After and back off.
* 599 UPSTREAM_UNREACHABLE:
  MCP server cannot reach internal API or timed out (check upstream health).

Health check (public):

```bash
curl -s "https://xcatcher.top/mcp/health"
```

## Pricing / quota (Points)

* Task creation consumes points (cost depends on mode and number of users).
* Exact cost may be returned as cost_points and remaining balance as balance_after.
* The server may enforce per-key rate limits and/or concurrency limits; violations return 429.

## Top-up / payment (if enabled)

```bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

# Create top-up order (returns on-chain payment details)
curl -s -X POST "$BASE/mcp/payment/create" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"amount_usd":20,"pay_currency":"eth"}'

# Check order status
PAYMENT_ID="5851596631"
curl -s "$BASE/mcp/payment/status/$PAYMENT_ID" \
  -H "Authorization: Bearer $API_KEY"
```

## Security & data handling

* Tasks are bound to the user derived from the Bearer token.
* Download links are authenticated. Do not share your Bearer token.
* Treat exported results as sensitive: they may contain third-party content and metadata.

## Support

* Developer docs: [https://xcatcher.top/docs/](https://xcatcher.top/docs/)
* Issues / requests: open an issue in this repository.

```
::contentReference[oaicite:0]{index=0}
```
