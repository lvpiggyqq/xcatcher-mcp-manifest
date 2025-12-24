#!/usr/bin/env bash
set -euo pipefail

# Auto-load .env if present (one-click friendly)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
fi

BASE="${BASE:-https://xcatcher.top}"
API_KEY="${API_KEY:-xc_live_xxx}"

MODE="${MODE:-deep}"
USERS_JSON="${USERS_JSON:-'["elonmusk"]'}"
IDEM="${IDEM:-curl402-$(date +%s)}"

NETWORK="${NETWORK:-}"             # base / solana
BASE_TXHASH="${BASE_TXHASH:-}"     # 0x...
SOL_SIGNATURE="${SOL_SIGNATURE:-}" # ...

TMPDIR="${TMPDIR:-/tmp}"
F_CREATE_1="$TMPDIR/mcp_create_1.json"
F_QUOTE="$TMPDIR/x402_quote.json"
F_TOPUP="$TMPDIR/x402_topup.json"
F_CREATE_2="$TMPDIR/mcp_create_2.json"
F_STATUS="$TMPDIR/mcp_status.json"
F_DL="$TMPDIR/mcp_download.json"

need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }; }
need_cmd curl; need_cmd jq; need_cmd base64

b64_encode() {
  # GNU coreutils base64 supports -w 0; macOS base64 doesn't
  if base64 -w 0 </dev/null >/dev/null 2>&1; then
    base64 -w 0
  else
    base64 | tr -d '\n'
  fi
}

b64_decode() {
  # GNU: base64 -d ; macOS: base64 -D
  if echo "e30=" | base64 -d >/dev/null 2>&1; then
    base64 -d
  else
    base64 -D
  fi
}

mcp_post() {
  curl -sS -X POST "$BASE/mcp/" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "$1"
}

# Important: compatible with FastMCP structuredContent wrapper
tool_result_filter='.result.structuredContent.result // .result'

echo "== 1) Health (/mcp/health) =="
curl -sS "$BASE/mcp/health" && echo

echo "== 2) Check current points (/api/v1/me) =="
curl -sS "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY" | jq .

echo "== 3) MCP create_crawl_task (expect 402 if points insufficient) =="
REQ_CREATE="$(jq -nc \
  --arg idem "$IDEM" \
  --arg mode "$MODE" \
  --argjson users "$USERS_JSON" \
  '{
    jsonrpc:"2.0",
    id:1,
    method:"tools/call",
    params:{
      name:"create_crawl_task",
      arguments:{mode:$mode, users:$users, idempotency_key:$idem}
    }
  }'
)"
mcp_post "$REQ_CREATE" | tee "$F_CREATE_1" >/dev/null

OK1="$(jq -r "$tool_result_filter | .ok // empty" "$F_CREATE_1")"
if [[ "$OK1" == "true" ]]; then
  echo "NOTE: create_crawl_task succeeded without 402 (you likely have enough points)."
  jq -r "$tool_result_filter" "$F_CREATE_1" | jq .
  exit 0
fi

CODE1="$(jq -r "$tool_result_filter | .error.code // empty" "$F_CREATE_1")"
if [[ "$CODE1" != "PAYMENT_REQUIRED" ]]; then
  echo "ERROR: create_crawl_task did not return PAYMENT_REQUIRED. code=$CODE1"
  jq -r "$tool_result_filter | .error // ." "$F_CREATE_1" | jq .
  exit 1
fi
echo "OK: got 402 / PAYMENT_REQUIRED."

echo "== 4) Extract + decode quote (payment_required_b64) =="
PR_B64="$(jq -r "$tool_result_filter | .error.details.payment_required_b64 // empty" "$F_CREATE_1")"
if [[ -z "$PR_B64" ]]; then
  echo "ERROR: missing payment_required_b64 in response."
  jq -r "$tool_result_filter | .error.details // .error // ." "$F_CREATE_1" | jq .
  exit 1
fi

printf '%s' "$PR_B64" | b64_decode > "$F_QUOTE"

QUOTE_ID="$(jq -r '.quote_id // empty' "$F_QUOTE")"
[[ -n "$QUOTE_ID" ]] || { echo "ERROR: quote decode failed or missing quote_id"; head -c 400 "$F_QUOTE"; echo; exit 1; }

# Print only key fields for readability
jq -r '{
  quote_id,
  expires_in,
  task_cost_points,
  balance_points,
  base_payTo:.accepts.base.payTo,
  base_amount:.accepts.base.maxAmountRequired,
  sol_payTo:.accepts.solana.payTo,
  sol_amount:.accepts.solana.maxAmountRequired
}' "$F_QUOTE" | jq .

echo "== 5) Provide payment proof (Base txHash or Solana signature) =="
if [[ -z "$NETWORK" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "Select network (base/solana, default base): " NETWORK || true
    NETWORK="${NETWORK:-base}"
  else
    [[ -n "$BASE_TXHASH" ]] && NETWORK="base"
    [[ -n "$SOL_SIGNATURE" ]] && NETWORK="solana"
  fi
fi

PAYMENT_SIGNATURE_B64=""
case "$NETWORK" in
  base)
    if [[ -z "$BASE_TXHASH" && -t 0 ]]; then
      read -r -p "Paste Base USDC transfer txHash (0x...): " BASE_TXHASH
    fi
    [[ -n "$BASE_TXHASH" ]] || { echo "ERROR: missing BASE_TXHASH"; exit 2; }
    PAYLOAD="$(jq -nc --arg tx "$BASE_TXHASH" \
      '{"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":$tx}}')"
    PAYMENT_SIGNATURE_B64="$(printf '%s' "$PAYLOAD" | b64_encode)"
    ;;
  solana)
    if [[ -z "$SOL_SIGNATURE" && -t 0 ]]; then
      read -r -p "Paste Solana USDC transfer signature: " SOL_SIGNATURE
    fi
    [[ -n "$SOL_SIGNATURE" ]] || { echo "ERROR: missing SOL_SIGNATURE"; exit 2; }
    PAYLOAD="$(jq -nc --arg sig "$SOL_SIGNATURE" \
      '{"x402Version":1,"scheme":"exact","network":"solana:mainnet","payload":{"signature":$sig}}')"
    PAYMENT_SIGNATURE_B64="$(printf '%s' "$PAYLOAD" | b64_encode)"
    ;;
  *)
    echo "ERROR: NETWORK must be base or solana"
    exit 2
    ;;
esac

echo "== 6) x402 topup for this API key (/api/v1/x402/topup) =="
curl -sS -X POST "$BASE/api/v1/x402/topup" \
  -H "Authorization: Bearer $API_KEY" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -H "Content-Type: application/json" \
  -d "$(jq -nc --arg q "$QUOTE_ID" '{quote_id:$q}')" \
  | tee "$F_TOPUP" | jq .

echo "== 6.1) Check points again (/api/v1/me) =="
curl -sS "$BASE/api/v1/me" -H "Authorization: Bearer $API_KEY" | jq .

echo "== 7) Retry MCP create_crawl_task (SAME idempotency_key) =="
mcp_post "$REQ_CREATE" | tee "$F_CREATE_2" >/dev/null

OK2="$(jq -r "$tool_result_filter | .ok // empty" "$F_CREATE_2")"
[[ "$OK2" == "true" ]] || { echo "ERROR: retry create still failed"; jq -r "$tool_result_filter | .error // ." "$F_CREATE_2" | jq .; exit 1; }

TASK_ID="$(jq -r "$tool_result_filter | .task_id // empty" "$F_CREATE_2")"
[[ -n "$TASK_ID" ]] || { echo "ERROR: missing task_id"; jq -r "$tool_result_filter" "$F_CREATE_2" | jq .; exit 1; }
echo "TASK_ID=$TASK_ID"

echo "== 8) Poll get_task_status until has_result=true =="
for i in $(seq 1 180); do
  REQ_STATUS="$(jq -nc --argjson tid "$TASK_ID" \
    '{jsonrpc:"2.0",id:10,method:"tools/call",params:{name:"get_task_status",arguments:{task_id:$tid}}}')"
  mcp_post "$REQ_STATUS" > "$F_STATUS"

  HAS="$(jq -r "$tool_result_filter | .has_result // false" "$F_STATUS")"
  ST="$(jq -r "$tool_result_filter | .status // \"-\"" "$F_STATUS")"
  echo "poll#$i status=$ST has_result=$HAS"
  [[ "$HAS" == "true" ]] && break
  sleep 5
done

echo "== 9) get_result_download_url + download =="
REQ_DL="$(jq -nc --argjson tid "$TASK_ID" \
  '{jsonrpc:"2.0",id:11,method:"tools/call",params:{name:"get_result_download_url",arguments:{task_id:$tid}}}')"
mcp_post "$REQ_DL" | tee "$F_DL" >/dev/null

DL_URL="$(jq -r "$tool_result_filter | .download_url // empty" "$F_DL")"
if [[ -z "$DL_URL" ]]; then
  echo "WARN: download_url missing; fallback to /api/v1/tasks/$TASK_ID/download"
  DL_URL="$BASE/api/v1/tasks/$TASK_ID/download"
fi
echo "DOWNLOAD_URL=$DL_URL"

OUT="task_${TASK_ID}.xlsx"
curl -sS -L -o "$OUT" -H "Authorization: Bearer $API_KEY" "$DL_URL"
echo "DONE: saved $(pwd)/$OUT"
