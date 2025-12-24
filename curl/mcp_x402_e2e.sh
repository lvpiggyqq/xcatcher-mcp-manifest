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

# Prefer normal mode in docs/examples because it's faster.
MODE="${MODE:-normal}"   # normal|deep

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

# Policy note (documented): minimum top-up is 0.50 USDC.
MIN_TOPUP_USDC="${MIN_TOPUP_USDC:-0.50}"

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

echo "== 0) Notes =="
echo " - Default MODE: $MODE (faster for copy-run)"
echo " - x402 payTo/amount are quote-specific and returned dynamically."
echo "   Therefore txHash/signature cannot be prepared in advance."
echo " - Minimum top-up: ${MIN_TOPUP_USDC} USDC (send at least this amount)"
echo " - If you need to re-run after paying, reuse the same IDEM for idempotency."
echo "   Current IDEM: $IDEM"
echo

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
echo "Quote summary (minimum_topup_usdc=${MIN_TOPUP_USDC}):"
jq -r --arg min "$MIN_TOPUP_USDC" '{
  quote_id,
  expires_in,
  task_cost_points,
  balance_points,
  minimum_topup_usdc:$min,
  base_payTo:(.accepts.base.payTo // null),
  base_amount:(.accepts.base.maxAmountRequired // null),
  sol_payTo:(.accepts.solana.payTo // null),
  sol_amount:(.accepts.solana.maxAmountRequired // null)
}' "$F_QUOTE" | jq .

echo
echo "== 5) Provide payment proof (Base txHash or Solana signature) =="
echo "Action required:"
echo "  1) Choose network (base/solana)"
echo "  2) Send USDC to the payTo address shown above"
echo "  3) Provide txHash (Base) or signature (Solana)"
echo "Minimum top-up: ${MIN_TOPUP_USDC} USDC"
echo

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
    PAYTO="$(jq -r '.accepts.base.payTo // empty' "$F_QUOTE")"
    AMT="$(jq -r '.accepts.base.maxAmountRequired // empty' "$F_QUOTE")"
    echo "Base payment details:"
    echo "  payTo : $PAYTO"
    echo "  amount: $AMT (atomic; USDC has 6 decimals)"
    echo "  minimum_topup_usdc: ${MIN_TOPUP_USDC}"
    echo

    if [[ -z "$BASE_TXHASH" ]]; then
      if [[ -t 0 ]]; then
        echo "Send USDC on Base to payTo, then paste the txHash."
        read -r -p "Paste Base USDC transfer txHash (0x...): " BASE_TXHASH
      else
        echo "Non-interactive run detected."
        echo "After you pay, re-run with:"
        echo "  NETWORK=base BASE_TXHASH=0x... IDEM=$IDEM bash $0"
        exit 2
      fi
    fi

    [[ -n "$BASE_TXHASH" ]] || { echo "ERROR: missing BASE_TXHASH"; exit 2; }
    PAYLOAD="$(jq -nc --arg tx "$BASE_TXHASH" \
      '{"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":$tx}}')"
    PAYMENT_SIGNATURE_B64="$(printf '%s' "$PAYLOAD" | b64_encode)"
    ;;
  solana)
    PAYTO="$(jq -r '.accepts.solana.payTo // empty' "$F_QUOTE")"
    AMT="$(jq -r '.accepts.solana.maxAmountRequired // empty' "$F_QUOTE")"
    echo "Solana payment details:"
    echo "  payTo : $PAYTO"
    echo "  amount: $AMT (atomic)"
    echo "  minimum_topup_usdc: ${MIN_TOPUP_USDC}"
    echo

    if [[ -z "$SOL_SIGNATURE" ]]; then
      if [[ -t 0 ]]; then
        echo "Send USDC on Solana to payTo, then paste the signature."
        read -r -p "Paste Solana USDC transfer signature: " SOL_SIGNATURE
      else
        echo "Non-interactive run detected."
        echo "After you pay, re-run with:"
        echo "  NETWORK=solana SOL_SIGNATURE=... IDEM=$IDEM bash $0"
        exit 2
      fi
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
