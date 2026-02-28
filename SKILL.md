---
name: xcatcher-mcp
description: Use Xcatcher Remote MCP and REST to create X crawl tasks, handle x402 topups, poll status, and download result files.
homepage: https://xcatcher.top/docs/
user-invocable: true
metadata: {"openclaw":{"emoji":"🐦","homepage":"https://xcatcher.top/docs/","requires":{"bins":["curl"],"env":["XCATCHER_API_KEY"]},"primaryEnv":"XCATCHER_API_KEY"}}
---

# Purpose

Use this skill when the user wants to crawl X/Twitter accounts through Xcatcher, monitor task progress, top up points with x402, or download result files.

Prefer the Xcatcher Remote MCP interface for task operations. Use REST for authentication, optional x402 quote inspection, and the final file download.

# Required runtime values

- Read the API key from `XCATCHER_API_KEY`.
- Default base URL: `https://xcatcher.top`
- Remote MCP URL: `https://xcatcher.top/mcp/`
- REST base: `https://xcatcher.top/api/v1`

For all Remote MCP JSON-RPC calls, always send these headers:

- `Authorization: Bearer $XCATCHER_API_KEY`
- `Accept: application/json`
- `Content-Type: application/json`

Critical rule: Xcatcher MCP is JSON-RPC over HTTP. Do not call URL paths like `/mcp/tools/list`. Always `POST` to `/mcp/` with a JSON-RPC body. If `Accept: application/json` is missing, the server can return JSON-RPC error `-32600`.

# Stable Remote MCP tools

Use these exact tool names:

- `create_crawl_task`
- `x402_topup`
- `get_task_status`
- `get_result_download_url`
- `cancel_task`

# Billing and task rules

- `mode: normal` costs 1 point per user.
- `mode: deep` costs 10 points per user.
- Always send a stable `idempotency_key` on `create_crawl_task`.
- If you must retry after payment or a transient error, reuse the same `idempotency_key`.
- If the request is large and the API rejects it, split user lists into smaller batches, typically 200 to 500 users per task.

# Default operating loop

## 1) Create the crawl task

Prefer Remote MCP.

Inputs:

- `users`: array of X usernames without the `@`
- `mode`: `normal` or `deep`
- `idempotency_key`: stable unique key for this logical request

Behavior:

- On success, store the returned `task_id`.
- On payment failure, branch into the x402 flow below.

## 2) If points are insufficient, handle `PAYMENT_REQUIRED`

When Xcatcher returns `PAYMENT_REQUIRED`, read the embedded payment details and extract:

- `quote_id`
- `accepts.base.payTo`
- `accepts.base.maxAmountRequired`
- `accepts.solana.payTo`
- `accepts.solana.maxAmountRequired`

Then complete payment on one supported chain:

### Base proof format

Use network `eip155:8453` and a tx-hash-only proof:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "eip155:8453",
  "payload": {
    "txHash": "0x...base_transaction_hash..."
  }
}
```

### Solana proof format

Use network `solana:mainnet` and a signature proof:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "solana:mainnet",
  "payload": {
    "signature": "5v...solana_tx_signature...pQ"
  }
}
```

Encode the raw UTF-8 JSON bytes as base64. Do not double-encode. Do not wrap the final base64 value in extra quotes.

Call `x402_topup` with:

- `quote_id`
- `payment_signature_b64`

Important: topup credits points to the current Bearer key. Keep using the same API key after topup.

After topup succeeds, retry `create_crawl_task` with the exact same `idempotency_key`.

## 3) Poll until the result is ready

Use `get_task_status` every 5 to 10 seconds until the task reports that a result is available.

Branching rules:

- `RATE_LIMITED` or HTTP 429: slow down and honor `Retry-After` if present.
- `RESULT_NOT_READY` or HTTP 409: keep polling.
- `UPSTREAM_UNREACHABLE`: report the upstream outage clearly.

## 4) Obtain the result download URL

Use `get_result_download_url` when the task is ready.

Important download rule:

- Result files are not public links.
- Always download with the same Bearer token.
- The final REST download is:
  - `GET /api/v1/tasks/{task_id}/download`
  - header: `Authorization: Bearer $XCATCHER_API_KEY`

Do not assume `/api/v1/tasks/{task_id}/result` returns JSON. Prefer the download URL or the explicit `/download` endpoint.

# JSON-RPC request templates

## List tools

```bash
curl -sS -X POST "https://xcatcher.top/mcp/" \
  -H "Authorization: Bearer $XCATCHER_API_KEY" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Health check

```bash
curl -sS "https://xcatcher.top/mcp/health"
```

# REST helpers

## Check current balance

```bash
curl -sS "https://xcatcher.top/api/v1/me" \
  -H "Authorization: Bearer $XCATCHER_API_KEY"
```

## Get a quote explicitly

Use this when you need to inspect the quote before paying, or when the user asks to top up a specific number of points manually.

```bash
curl -sS "https://xcatcher.top/api/v1/x402/quote?points=100"
```

## Download the result file

```bash
curl -sS -L "https://xcatcher.top/api/v1/tasks/12345/download" \
  -H "Authorization: Bearer $XCATCHER_API_KEY" \
  -o task_12345.xlsx
```

# Execution preferences

- Prefer Remote MCP for task lifecycle actions.
- Prefer REST only for `/me`, optional `/x402/quote`, and the final file download.
- Be explicit about point consumption before creating large jobs.
- When the user provides many usernames, confirm or summarize the estimated cost before sending a large batch.
- When a task completes, tell the user the `task_id`, the mode used, the charged points, and where the file was saved.
- If the API key is missing, instruct the user to set `XCATCHER_API_KEY` in the environment or under `skills.entries.xcatcher-mcp.env.XCATCHER_API_KEY` in `~/.openclaw/openclaw.json`.

# Failure handling

- 401 `AUTH_MISSING` or `AUTH_INVALID`: the Bearer token is missing or invalid.
- 402 `PAYMENT_REQUIRED`: pay, top up, then retry with the same `idempotency_key`.
- 409 `RESULT_NOT_READY`: poll again later.
- 429 `RATE_LIMITED`: slow down and retry after the advised delay.
- 599 `UPSTREAM_UNREACHABLE`: surface the outage and stop retrying aggressively.

# Minimal success path summary

1. `create_crawl_task`
2. If 402: pay on Base or Solana, then `x402_topup`
3. Retry `create_crawl_task` with the same `idempotency_key`
4. `get_task_status` until ready
5. `get_result_download_url`
6. `GET /api/v1/tasks/{task_id}/download` with the same Bearer token
