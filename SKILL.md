---
name: x402-x-tweet-fetcher
description: Top up Xcatcher points via x402 on Solana (USDC), obtain an API key, create X crawl tasks, poll status, and download XLSX results.
homepage: https://xcatcher.top/docs/
user-invocable: true
metadata: {"openclaw":{"emoji":"🐦","homepage":"https://xcatcher.top/docs/","requires":{"bins":["curl","jq","base64"],"env":["XCATCHER_API_KEY"]},"primaryEnv":"XCATCHER_API_KEY"}}
---

# Xcatcher (x402 + Tasks)

Use this skill to:
- buy points via x402 on Solana (USDC),
- obtain an API key,
- create crawl tasks,
- poll task status,
- download XLSX results.

Base URL: https://xcatcher.top  
REST base: https://xcatcher.top/api/v1  
Optional health: https://xcatcher.top/mcp/health

## Requirements
- curl, jq, base64
- Set `XCATCHER_API_KEY` for authenticated calls (you will obtain it in step 4 if you don't have one).

## Points pricing (task cost)
- mode=normal: 1 point / user
- mode=deep: 10 points / user
- estimated_cost = users_count × (mode == normal ? 1 : 10)
- support chain: base / sol

> Do not hardcode any USDC→points rate. Always trust the quote response.

---

## 0) Optional health check
BASE="https://xcatcher.top"
curl -sS "$BASE/mcp/health"
echo

---

## 1) Get an x402 quote (points → Solana USDC payment instructions)
Notes:
- Quotes expire quickly (often ~60s). Pay immediately after receiving the quote.

BASE="https://xcatcher.top"
POINTS=1

curl -sS "$BASE/api/v1/x402/quote?points=$POINTS" | tee quote.json
echo

QUOTE_ID=$(jq -r '.quote_id' quote.json)
USDC_MINT=$(jq -r '.accepts.solana.asset' quote.json)
PAY_TO=$(jq -r '.accepts.solana.payTo' quote.json)
AMOUNT_ATOMIC=$(jq -r '.accepts.solana.maxAmountRequired' quote.json)

echo "QUOTE_ID=$QUOTE_ID"
echo "USDC_MINT=$USDC_MINT"
echo "PAY_TO=$PAY_TO"
echo "AMOUNT_ATOMIC=$AMOUNT_ATOMIC"
echo "USDC_AMOUNT=$(python3 - <<'PY'
import json
q=json.load(open("quote.json"))
amt=int(q["accepts"]["solana"]["maxAmountRequired"])
print(amt/1_000_000)
PY
)"
echo
QUOTE_ID must save
---

## 2) Pay USDC on Solana mainnet
Send USDC (SPL) to PAY_TO for at least AMOUNT_ATOMIC (USDC has 6 decimals).  
Record the Solana transaction signature, then set it below.

SOL_SIG="YOUR_SOLANA_TX_SIGNATURE"

---

## 3) Build PAYMENT-SIGNATURE header (base64 of UTF-8 JSON)
Rules:
- Base64 encode once (no double encoding).
- Do not wrap the header value in extra quotes.

PAYMENT_SIGNATURE_B64=$(jq -nc --arg sig "$SOL_SIG" \
  '{"x402Version":1,"scheme":"exact","network":"solana:mainnet","payload":{"signature":$sig}}' \
  | base64 | tr -d '\n')

echo "PAYMENT_SIGNATURE_B64=$PAYMENT_SIGNATURE_B64"
echo

---

## 4) Buy points (quote_id + PAYMENT-SIGNATURE → api_key)
BASE="https://xcatcher.top"

curl -sS -X POST "$BASE/api/v1/x402/buy_points" \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -d "$(jq -nc --arg q "$QUOTE_ID" '{quote_id:$q}')" \
  | tee buy.json
echo

API_KEY=$(jq -r '.api_key' buy.json)
echo "API_KEY=$API_KEY"
export XCATCHER_API_KEY="$API_KEY"
echo "XCATCHER_API_KEY exported."
echo

---

## 5) Verify balance (must-do)
BASE="https://xcatcher.top"
curl -sS "$BASE/api/v1/me" \
  -H "Authorization: Bearer $XCATCHER_API_KEY" \
  | jq .
echo

If you get 402 here or later:
- Most common causes: quote expired or payment proof invalid.
- Fix: redo steps 1 → 4 with a NEW quote and NEW payment.

---

## 6) Create crawl task
Rules:
- users are X usernames without '@'
- always provide idempotency_key
- if retrying the same logical request, reuse the same idempotency_key

BASE="https://xcatcher.top"
MODE="normal"
IDEM="test-idem-001"
USERS_JSON='["user1","user2"]'

echo "ESTIMATED_COST_POINTS=$(python3 - <<'PY'
import json, os
users=json.loads(os.environ.get("USERS_JSON","[]"))
mode=os.environ.get("MODE","normal")
per=1 if mode=="normal" else 10
print(len(users)*per)
PY
)"
echo

curl -sS -X POST "$BASE/api/v1/tasks" \
  -H "Authorization: Bearer $XCATCHER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -nc --arg mode "$MODE" --arg idem "$IDEM" --argjson users "$USERS_JSON" \
        '{mode:$mode, users:$users, idempotency_key:$idem}')" \
  | tee task.json | jq .
echo

TASK_ID=$(jq -r '.task_id' task.json)
echo "TASK_ID=$TASK_ID"
echo

---

## 7) Poll task status until ready
Stop when download_url or result_path is present.

BASE="https://xcatcher.top"
while true; do
  J=$(curl -sS "$BASE/api/v1/tasks/$TASK_ID" -H "Authorization: Bearer $XCATCHER_API_KEY")
  echo "$J" | jq '{task_id,status,status_code,updated_time,error_message,result_path,download_url}'
  HAS=$(echo "$J" | jq -r '(.download_url // .result_path // "") | length')
  if [ "$HAS" -gt 0 ]; then
    echo "DONE"
    break
  fi
  sleep 5
done
echo

---

## 8) Download result (XLSX)
Download requires the same Bearer token; results are not public.

BASE="https://xcatcher.top"
curl -sS -L -o "task_${TASK_ID}.xlsx" \
  -H "Authorization: Bearer $XCATCHER_API_KEY" \
  "$BASE/api/v1/tasks/$TASK_ID/download"

echo "Saved: task_${TASK_ID}.xlsx"
echo

---

## Failure handling
- 401: Bearer token missing/invalid → obtain API key via buy_points or set XCATCHER_API_KEY correctly.
- 402: quote/proof invalid or expired → redo quote + pay + buy_points (steps 1–4).
- 429: rate limited → backoff; respect Retry-After if present.
- Task stuck / upstream issues → report clearly; poll with increasing interval if needed.
