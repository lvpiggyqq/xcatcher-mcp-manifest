# Xcatcher MCP (Remote)

Remote MCP / x402 / USDC / Base / Solana / OpenAPI / Google ADK / Gemini
Xcatcher is an agent-first **Remote MCP** server (Streamable HTTP) for high-throughput crawling of **fresh/latest posts** across large sets of X (Twitter) usernames.
It supports **x402** pay-as-you-go top-ups using **USDC** on **Base** and **Solana**, and ships an **OpenAPI** spec for direct import by agent builders.

[![Glama MCP](https://glama.ai/mcp/servers/@lvpiggyqq/xcatcher-mcp-manifest/badge)](https://glama.ai/mcp/servers/@lvpiggyqq/xcatcher-mcp-manifest)
[![Smithery](https://img.shields.io/badge/Smithery-Listing-0b5fff)](https://smithery.ai/search?q=xcatcher)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0.3-6BA539)](./openapi/xcatcher.yaml)

## Copy-paste quickstart (3 commands)
```bash
# 1) Google ADK end-to-end (Remote MCP + x402)
cd google-adk && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && \
XCAT_BASE="https://xcatcher.top" XCAT_API_KEY="xc_live_xxx" XCAT_MODE="normal" python adk_mcp_e2e.py

# 2) curl end-to-end (Remote MCP create -> 402 -> quote decode -> topup -> retry -> download)
cd curl && cp env.example .env && sed -i.bak 's/xc_live_xxx/xc_live_xxx/' .env && bash mcp_x402_e2e.sh

# 3) Quote (points -> USDC invoice) + (after you pay) topup
curl -s "https://xcatcher.top/api/v1/x402/quote?points=100" | jq .
Directory listings (discovery)
Glama: https://glama.ai/mcp/servers/@lvpiggyqq/xcatcher-mcp-manifest

Smithery: https://smithery.ai/search?q=xcatcher

Endpoints
Base URL: https://xcatcher.top

Remote MCP (Streamable HTTP): https://xcatcher.top/mcp/

REST API base: https://xcatcher.top/api/v1

Docs: https://xcatcher.top/docs/

Health (public): https://xcatcher.top/mcp/health

Authentication
All MCP and REST calls require:

Authorization: Bearer xc_live_...

Acquire an API key via REST:

POST /api/v1/auth/register (creates account + returns api_key)

POST /api/v1/auth/login (returns api_key, may revoke older keys)

Important:

Result files are not public direct links. Always download via authenticated endpoints using the same Bearer token.

OpenAPI import
Raw spec (copy into an agent builder / API tool):
https://raw.githubusercontent.com/lvpiggyqq/xcatcher-mcp-manifest/main/openapi/xcatcher.yaml
Recommended usage:

Import the OpenAPI spec to quickly wire REST calls (points, quote/topup, downloads).

Use Remote MCP for tool-style orchestration (create -> poll -> download), especially with agent frameworks.

Output format
Default export: XLSX

If CSV is needed, convert the downloaded XLSX to CSV client-side.

Modes: normal vs deep
Default recommendation: normal (faster, lower latency for “latest posts” monitoring).

normal (recommended)
Purpose: fast “latest posts” snapshot at scale

Best for: monitoring, alerting, pipelines that repeatedly fetch new posts

deep (optional)
Purpose: deeper per-user collection / enrichment

Best for: deeper historical/contextual pulls where latency is less critical

Notes:

Exact cost and remaining balance are returned by the server when you create a task (e.g., cost_points, balance_after).

Remote MCP tools (high level)
Xcatcher exposes a small, agent-friendly core:

create_crawl_task (side effect: consumes points)

x402_topup (side effect: credits points after on-chain payment proof)

get_task_status (poll until done)

get_result_download_url (returns authenticated download URL)

cancel_task (cancel a queued task; policy may refund)

Agents should rely on the tool schema (tools/list) for exact input fields, constraints, and server-side validation rules.

Remote MCP JSON-RPC (cURL)
MCP is JSON-RPC over HTTP. You must include Accept: application/json.

bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"

curl -sS -X POST "$BASE/mcp/" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
Quickstart (Google ADK → Remote MCP)
See: ./google-adk/README.md

One-liner:

bash
cd google-adk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
XCAT_BASE="https://xcatcher.top" XCAT_API_KEY="xc_live_xxx" XCAT_MODE="normal" python adk_mcp_e2e.py
Quickstart (REST API)
Workflow: create task → poll → download.

bash
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
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
TASK_ID=10136

# Poll
curl -s "$BASE/api/v1/tasks/$TASK_ID" -H "Authorization: Bearer $API_KEY"

# Download (xlsx stream)
curl -L -o "task_${TASK_ID}.xlsx" \
  -H "Authorization: Bearer $API_KEY" \
  "$BASE/api/v1/tasks/$TASK_ID/download"
x402 Top-up (Base / Solana)
When you create a task with insufficient points, you may get HTTP 402 with a PAYMENT-REQUIRED header (base64 JSON) and a body containing a quote (quote_id, payTo, maxAmountRequired, etc.).

Practical workflow (because payTo is quote-specific and you cannot know txHash/signature in advance):

Request a quote (or trigger 402 to receive one)

Pay USDC to the returned payTo

Paste the resulting txHash/signature into PAYMENT-SIGNATURE, then top up

Minimum payment note:

Minimum top-up is 0.5 USDC (paying less may fail verification).

PAYMENT-SIGNATURE format
Topup proof is sent as HTTP header: PAYMENT-SIGNATURE

Value = base64(UTF-8 JSON):

Base proof uses txHash

Solana proof uses signature

Base example:

json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "eip155:8453",
  "payload": { "txHash": "0x...base_transaction_hash..." }
}
Solana example:

json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "solana:mainnet",
  "payload": { "signature": "5v...solana_tx_signature...pQ" }
}
Base: quote → pay USDC → topup → /me
bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
POINTS=100

# 1) Quote
curl -s "$BASE/api/v1/x402/quote?points=$POINTS" | jq .

# 2) Pay on Base:
# - send USDC to quote.accepts.base.payTo
# - amount >= quote.accepts.base.maxAmountRequired (atomic, 6 decimals)
QUOTE_ID="q_xxx"
BASE_TXHASH="0x...your_base_tx_hash..."

# 3) PAYMENT-SIGNATURE = base64(json)
PAYMENT_SIGNATURE_B64=$(jq -nc --arg tx "$BASE_TXHASH" \
  '{"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":$tx}}' \
  | base64 -w 0)

# macOS fallback:
# PAYMENT_SIGNATURE_B64=$(jq -nc --arg tx "$BASE_TXHASH" \
#   '{"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":$tx}}' \
#   | base64 | tr -d '\n')

# 4) Top up CURRENT key
curl -s -X POST "$BASE/api/v1/x402/topup" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -d "{\"quote_id\":\"$QUOTE_ID\"}" | jq .

# 5) Verify points
curl -s "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY" | jq .
Solana: quote → SPL transfer → topup → /me
bash
BASE="https://xcatcher.top"
API_KEY="xc_live_xxx"
POINTS=100

# 1) Quote
curl -s "$BASE/api/v1/x402/quote?points=$POINTS" | jq .

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
  -d "{\"quote_id\":\"$QUOTE_ID\"}" | jq .

# 5) Verify points
curl -s "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY" | jq .
After topup:

Retry create_crawl_task / POST /api/v1/tasks using the same idempotency_key that triggered 402.

REST Endpoints Summary
POST /api/v1/auth/register — create account + issue api_key

POST /api/v1/auth/login — login + issue api_key (may revoke old key)

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