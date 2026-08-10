# Xcatcher API reference

Base URL: `https://xcatcher.top`. OpenAPI: `https://xcatcher.top/openapi.yaml`.

## Preferred endpoints

| Purpose | Method and path | Auth | Side effect |
|---|---|---|---|
| Service capabilities | `GET /api/v1/capabilities` | No | No |
| Crawl preflight | `POST /api/v1/preflight` | No | No; no quote or task |
| Synthetic result example | `GET /api/v1/demo` | No | No; never fetches X |
| MCP health | `GET /mcp/health` | No | No |
| MCP tools | `POST /mcp/` | Optional Bearer | Depends on tool |
| Direct crawl challenge | `POST /api/v1/x402/crawl` | No | Creates expiring quote |
| Submit direct payment | same path + `PAYMENT-SIGNATURE` | x402 v2 proof | May settle USDC and create task |
| Direct task | `GET /api/v1/x402/tasks/{id}` | `Bearer xtask_...` | No |
| Direct JSON results | `GET /api/v1/x402/tasks/{id}/results` | `Bearer xtask_...` | No |
| Direct XLSX | `GET /api/v1/x402/tasks/{id}/download` | `Bearer xtask_...` | No |
| Register / login | `POST /api/v1/auth/register` or `/login` | No | Creates account or key |
| Account / points | `GET /api/v1/me` | API key | No |
| List / create tasks | `GET` or `POST /api/v1/tasks` | API key | POST consumes points |
| Task status | `GET /api/v1/tasks/{id}` | API key | No |
| JSON results | `GET /api/v1/tasks/{id}/results` | API key | No |
| XLSX result | `GET /api/v1/tasks/{id}/download` | API key | No |
| Cancel queued task | `POST /api/v1/tasks/{id}/cancel` | API key | Cancels and refunds |
| List / create keys | `GET` or `POST /api/v1/keys` | `keys:manage` | POST creates secret |
| Revoke key | `DELETE /api/v1/keys/{key_id}` | `keys:manage` | Revokes key |

Retired unauthenticated `/api/login`, `/api/user/points`, `/api/twitter/*`, `/api/deduct_points`, and `/api/create_order` endpoints return `410 LEGACY_ENDPOINT_GONE`.

## Crawl input

```json
{
  "mode": "normal",
  "users": ["openai", "https://x.com/naval"],
  "idempotency_key": "monitor-2026-08-07-openai-naval"
}
```

- `users`: 1–500 handles, `@handles`, or X/Twitter profile URLs; deduplicated case-insensitively.
- API-key accounts: `normal` costs one point and `deep` costs ten points per normalized requested handle.
- Accountless x402 `normal`: progressive pricing — handles 1–5 cost `$0.01` each, 6–25 cost `$0.0075` each, 26–100 cost `$0.006` each, and 101–500 cost `$0.005` each. Tiers are progressive rather than a single rate applied to the whole task; minimum task price is `$0.01`.
- Accountless x402 `deep`: `$0.10` per normalized requested handle. Internal Actor failover is included without an additional charge.
- Call free preflight with the complete deduplicated list for the exact modeled amount; the later live 402 remains authoritative.
- `idempotency_key`: API-key task only, at most 128 safe characters. Reuse it for the identical logical request.

## Task and result state

| Status | Meaning | Action |
|---|---|---|
| `queued` | Accepted | Poll after 5–10 seconds |
| `processing` | Upstream collection active | Keep polling with backoff |
| `done` | Structured result and XLSX available | Read `/results` or download |
| `failed` | Terminal upstream/task failure | Inspect safe `error.code`; do not retry blindly |
| `cancelled` | Queued task cancelled/refunded | Stop |

`result_meta` reports `row_count`, bounded upstream fetch policy, total fetch elapsed time, and per-handle outcomes. A handle outcome can be `ok`, `no_posts`, or `failed` and includes `attempts` plus `elapsed_ms`. `no_posts` carries `NO_PUBLIC_POSTS_OR_HANDLE_UNAVAILABLE`: it may mean an empty public result, an unavailable/private account, or an incorrect handle, so it is not proof that the account never posted. A completed task can contain partial coverage. REST `/results` accepts `limit=1..200`; MCP preview tools accept at most 100 rows per call. Both use `offset>=0` and return `rows`, `total`, and `next_offset`.

## API keys

API keys are independently revocable. New keys can be named, scoped, and given a 1–365 day expiry. Supported scopes are:

- `account:read`
- `tasks:read`
- `tasks:write`
- `results:read`
- `payments:write`
- `keys:manage`

Only the new key secret is returned at creation. Store it securely; listing keys returns metadata and prefixes, never key secrets.

## MCP tools

Discovery and accountless tools work without an API key:

- `get_service_info`
- `preflight_crawl`, `get_sample_result`
- `get_direct_crawl_payment`
- `submit_direct_crawl_payment`
- `get_direct_task_status`
- `get_direct_result_preview`

API-key tools:

- `get_account_balance`, `list_crawl_tasks`
- `create_crawl_task`, `get_task_status`, `wait_for_task`, `cancel_task`
- `get_result_preview`, `get_result_download_url`
- `get_x402_quote`, `x402_topup` (account credit compatibility flow)

Call `tools/list` for authoritative JSON Schemas and annotations.

## Error handling

Errors use `error.code`, `error.message`, optional `error.details`, and `request_id`. Important actions:

| HTTP / code | Action |
|---|---|
| `400 VALIDATION_ERROR` | Fix inputs; keep the idempotency key if intent is unchanged |
| `401 AUTH_*` / `TASK_TOKEN_INVALID` | Supply the correct non-expired credential |
| `402 PAYMENT_*` | Inspect both `PAYMENT-REQUIRED` and `PAYMENT-RESPONSE`; never submit a second payment blindly |
| `404 TASK_NOT_FOUND` | Verify task ID and owning credential; do not enumerate IDs |
| `409 IDEMPOTENCY_KEY_CONFLICT` | Use a new key only if request intent changed |
| `409 RESULT_NOT_READY` | Continue polling the same task |
| `429 RATE_LIMITED` | Honor `Retry-After`, reduce concurrency, increase polling interval |
| `5xx` | Retry with backoff using the same task/signature; do not recreate or repay |

## REST fallback

Run `python3 scripts/xcatcher.py --help`. Start with `capabilities`, then use `preflight HANDLE...` and optionally `demo`. The helper can preview a direct x402 challenge but intentionally cannot submit a payment. Authenticated commands read `XCATCHER_API_KEY` or `XCATCHER_TASK_TOKEN` only from the process environment; they never accept credentials as command-line arguments. Use an approved wallet connector for payment submission.
