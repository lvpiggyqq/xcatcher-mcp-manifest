# Xcatcher MCP (Remote)

Xcatcher is an agent-first **Remote MCP** server (Streamable HTTP) plus a REST API for high-throughput crawling of **fresh/latest posts** across large sets of X (Twitter) usernames.  
It supports **x402** pay-as-you-go top-ups using **USDC** on **Base** and **Solana**, and ships an **OpenAPI** spec for direct import by agent builders.  
It includes copy-paste end-to-end examples for **Google ADK** and **Gemini** agents, plus curl scripts for MCP + x402 flows.  
Results are returned as an authenticated **XLSX** download (convert to CSV client-side if needed).

## Endpoints

- Base URL: `https://xcatcher.top`
- Remote MCP (Streamable HTTP): `https://xcatcher.top/mcp/`
- REST API base: `https://xcatcher.top/api/v1`
- Docs: `https://xcatcher.top/docs/`
- Health (public): `https://xcatcher.top/mcp/health`

## Authentication

All MCP and REST calls require:

- `Authorization: Bearer xc_live_...`

Acquire an API key via REST:

- `POST /api/v1/auth/register` (creates account + returns `api_key`)
- `POST /api/v1/auth/login` (returns `api_key`, may revoke older keys)

Important:
- Result files are **not public direct links**. Always download via authenticated endpoints using the same Bearer token.

---

## Output format

- Default export: **XLSX**
- Compatibility tip: If CSV is needed, convert the downloaded XLSX to CSV client-side.

---

## Modes: normal vs deep

Choose the mode based on your goal:

### `normal` (recommended for monitoring / fresh feed)
- Purpose: fast “latest posts” snapshot at scale
- Best for: high-concurrency monitoring, alerting, pipelines that repeatedly fetch new posts
- Typical: fastest turnaround and highest throughput

### `deep`
- Purpose: deeper per-user collection / enrichment
- Best for: deeper historical/contextual pulls where latency is less critical
- Typical: slower than normal and uses more resources

Notes:
- Exact cost and remaining balance are returned by the server when you create a task (e.g., `cost_points`, `balance_after`).

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

Xcatcher exposes a small, agent-friendly core:

- `create_crawl_task` (side effect: consumes points)
- `x402_topup` (side effect: credits points after on-chain payment proof)
- `get_task_status` (poll until done)
- `get_result_download_url` (returns authenticated download URL)
- `cancel_task` (cancel a queued task; policy may refund)

Agents should rely on the tool schema (`tools/list`) for exact input fields, constraints, and server-side validation rules.

---

## Remote MCP JSON-RPC (cURL)

MCP is JSON-RPC over HTTP. **You must include `Accept: application/json`.**

```bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

curl -sS -X POST "$BASE/mcp/" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
Quickstart (Google ADK → Remote MCP)
python
复制代码
import os

# ADK import compat
try:
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
except Exception:
    from google.adk.tools.mcp_tool import MCPToolset as McpToolset  # type: ignore
    from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams  # type: ignore

toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://xcatcher.top/mcp",
        headers={
            "Authorization": "Bearer xc_live_xxx",
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
Recommended agent flow:

create_crawl_task with mode and users (+ idempotency_key recommended)

poll get_task_status every ~5 seconds

get_result_download_url, then download using the same Bearer token

if 402 (PAYMENT_REQUIRED): perform x402 topup then retry create with the same idempotency_key

Quickstart (REST API)
Workflow: create task → poll → download.

bash
复制代码
BASE="https://xcatcher.top"

# 1) Register -> returns api_key (xc_live_...)
curl -s -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

# 2) Login -> returns api_key (may revoke old key)
curl -s -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

API_KEY="xc_live_xxx"

# 3) Check points
curl -s "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY"

# 4) Create task (side-effect: consumes points; may return 402)
curl -s -X POST "$BASE/api/v1/tasks" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"normal","users":["elonmusk","naval"],"idempotency_key":"rest-req-001"}'
Poll + download:

bash
复制代码
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
TASK_ID=10136

# Poll
curl -s "$BASE/api/v1/tasks/$TASK_ID" -H "Authorization: Bearer $API_KEY"

# Download (xlsx stream)
curl -L -o "task_${TASK_ID}.xlsx" \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE/api/v1/tasks/$TASK_ID/download"
Polling guidance:

Poll every 5–10 seconds under normal conditions.

If you receive 429, back off and honor Retry-After.

Idempotency:

Always pass idempotency_key for create calls to prevent double charges during retries.

x402 Top-up (Base / Solana)
When you create a task with insufficient points, you may get HTTP 402 with a PAYMENT-REQUIRED header (base64 JSON) and a body containing a quote (quote_id, payTo, maxAmountRequired, etc.). Use x402:

Two steps: GET quote → pay on-chain → POST topup.

PAYMENT-SIGNATURE format
Topup proof is sent as HTTP header: PAYMENT-SIGNATURE

Value = base64(UTF-8 JSON):

Base proof uses txHash

Solana proof uses signature

Base example (txHash-only):

json
复制代码
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "eip155:8453",
  "payload": { "txHash": "0x...base_transaction_hash..." }
}
Solana example (tx signature):

json
复制代码
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "solana:mainnet",
  "payload": { "signature": "5v...solana_tx_signature...pQ" }
}
Encoding note:

base64 must be computed on the raw JSON UTF-8 bytes.

Do not double-encode. Do not wrap in extra quotes.

Base: quote → pay USDC → topup → /me
bash
复制代码
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
POINTS=100

# 1) Quote
QUOTE_JSON=$(curl -s "$BASE/api/v1/x402/quote?points=$POINTS")
echo "$QUOTE_JSON"

# 2) Pay on Base:
# - send USDC to quote.accepts.base.payTo
# - amount >= quote.accepts.base.maxAmountRequired (atomic, 6 decimals)
QUOTE_ID="q_xxx"
BASE_TXHASH="0x...your_base_tx_hash..."

# 3) PAYMENT-SIGNATURE = base64(json)
PAYMENT_SIGNATURE_B64=$(jq -nc --arg tx "$BASE_TXHASH" \
  '{"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":$tx}}' \
  | base64 -w 0)

# 4) Top up CURRENT key
curl -s -X POST "$BASE/api/v1/x402/topup" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -d "{\"quote_id\":\"$QUOTE_ID\"}"

# 5) Verify points
curl -s "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY"
macOS note: if base64 -w 0 fails, use base64 | tr -d '\n' to ensure single-line output.

Solana: quote → SPL transfer → topup → /me
bash
复制代码
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
POINTS=100

# 1) Quote
curl -s "$BASE/api/v1/x402/quote?points=$POINTS"

# 2) Pay on Solana:
# - send USDC SPL to quote.accepts.solana.payTo
QUOTE_ID="q_xxx"
SOL_TX_SIG="5v...your_solana_signature...pQ"

# 3) PAYMENT-SIGNATURE = base64(json)
PAYMENT_SIGNATURE_B64=$(jq -nc --arg sig "$SOL_TX_SIG" \
  '{"x402Version":1,"scheme":"exact","network":"solana:mainnet","payload":{"signature":$sig}}' \
  | base64 -w 0)

# 4) Top up CURRENT key
curl -s -X POST "$BASE/api/v1/x402/topup" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -d "{\"quote_id\":\"$QUOTE_ID\"}"

# 5) Verify points
curl -s "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY"
After topup:

Retry POST /api/v1/tasks using the same idempotency_key that triggered 402.

REST Endpoints Summary
POST /api/v1/auth/register — create account + issue api_key

POST /api/v1/auth/login — login + issue api_key (may revoke older keys)

GET /api/v1/me — check current user + points for Bearer key

POST /api/v1/tasks — create a task (consumes points; returns 402 if low)

GET /api/v1/tasks/<id> — read task status

GET /api/v1/tasks/<id>/download — download result file (requires Bearer)

POST /api/v1/tasks/<id>/cancel — cancel queued task (policy may refund)

GET /api/v1/x402/quote?points=<n> — get x402 quote by points

POST /api/v1/x402/topup — top up current Bearer key using PAYMENT-SIGNATURE

Error handling (agent branching)
401 AUTH_MISSING / AUTH_INVALID: missing/invalid Bearer token

402 PAYMENT_REQUIRED: pay + topup then retry (same idempotency_key)

409 RESULT_NOT_READY: keep polling

429 RATE_LIMITED: back off, honor Retry-After

599 UPSTREAM_UNREACHABLE: internal dependency unreachable

5xx: transient errors; retry with exponential backoff

Support
Docs: https://xcatcher.top/docs/

Issues / requests: open an issue in this repository.