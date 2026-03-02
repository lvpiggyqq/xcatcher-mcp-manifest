---
name: x402-twitter-fetcher-entry
description: x402 Fetch Twitter/X main entry: compute points_buy from “N accounts + mode (normal/deep)”, then follow the fixed flow: get quote → pay USDC on-chain (Base/Solana) → exchange payment proof (txHash/signature) for “temporary account + API Key (xc_live_*)” → use that key to create crawl task → get task status → get result download URL → download the results.
requires:
  bins:
    - curl
os:
  - linux
  - darwin
---

# x402 Fetch Twitter/X Entry (N+mode → quote → pay → exchange key → create_crawl_task → get_task_status → get_result_download_url → download)

## The flow (fixed, do not skip steps)
N handles + mode (normal/deep)  
→ get quote  
→ pay USDC on-chain (Base or Solana)  
→ exchange payment proof for “temporary account + API Key (xc_live_*)”  
→ use that key to create crawl task  
→ get task status  
→ get result download URL  
→ download the results

## Inputs (confirm first)
- base_url: https://xcatcher.top
- N: number of handles to crawl (integer)
- MODE: normal or deep
- CHAIN: base or solana
- Payment proof (one of):
  - Base: txHash
  - Solana: signature
- Optional: USERS (array of handles)

## Pricing & points formula (do this first)
- normal: 1 point / handle
- deep: 10 points / handle

Formula:
- rate = 1 (normal) OR 10 (deep)
- points_needed = N * rate
- points_buy = points_needed

Examples:
- N=200, normal → needed=200 
- N=200, deep → needed=2000  

## Safety boundaries (mandatory)
- Never request/accept: private keys, seed phrases, exchange API keys, exported wallet files.
- x402 needs payment proof only: Base txHash / Solana signature.
- xc_live_* is sensitive: instruct user to save it immediately; do not leak it in logs/public chats/screenshots.
- If server returns 409 / already processed: do not re-submit the same proof; start a new quote + new payment.

## Steps (strict order)

### Step 0 — Compute points_buy from N + MODE
Compute points_buy and tell the user:  
“You want N handles in MODE, you need to buy points_buy points.”

### Step 1 — Get quote
base_url="https://xcatcher.top"  
POINTS_BUY="240"   # computed in Step 0  
curl -sS "${base_url}/api/v1/x402/quote?points=${POINTS_BUY}" | tee /tmp/x402_quote.json  

Extract (for selected CHAIN):  
- quote_id  
- payTo  
- asset  
- maxAmountRequired  
- expires_in  

Send “chain/payTo/amount/ttl” to the user to complete on-chain payment.

### Step 2 — Pay USDC on-chain
User pays following the quote instructions:  
- CHAIN=base: transfer USDC to accepts.base.payTo with accepts.base.maxAmountRequired, then return txHash  
- CHAIN=solana: transfer SPL USDC to accepts.solana.payTo with accepts.solana.maxAmountRequired, then return signature

### Step 3 — Exchange proof for “temporary account + API Key (xc_live_*)”
PAYMENT-SIGNATURE = base64(utf8-json). JSON must include quote + proof only.

Base JSON (proof=txHash):

{
  "x402Version": 1,
  "scheme": "exact",
  "quoteId": "<QUOTE_ID>",
  "chain": "base",
  "proof": { "txHash": "<TX_HASH>" },
  "idempotencyKey": "<ANY_STRING>"
}

Solana JSON (proof=signature):

{
  "x402Version": 1,
  "scheme": "exact",
  "quoteId": "<QUOTE_ID>",
  "chain": "solana",
  "proof": { "signature": "<SIGNATURE>" },
  "idempotencyKey": "<ANY_STRING>"
}

Submit:

PAYMENT_SIGNATURE_B64="<<<BASE64_JSON_HERE>>>"

curl -sS -X POST "${base_url}/api/v1/x402/buy_points" \
  -H "Content-Type: application/json" \
  -H "PAYMENT-SIGNATURE: ${PAYMENT_SIGNATURE_B64}" \
  -d "{\"points\": ${POINTS_BUY} }" | tee /tmp/x402_buy_points_ok.json

Success response should contain:
  - api_key: xc_live_*  
  - username: x402_*  
Tell user to save xc_live_* immediately.

### Step 4 — Verify via /me
API_KEY="<<<XC_LIVE_KEY_HERE>>>"

curl -sS "${base_url}/api/v1/me" \
  -H "Authorization: Bearer ${API_KEY}" | tee /tmp/x402_me.json

### Step 5 — Create the crawl task (/api/v1/tasks)
MODE="normal"  # or deep  
curl -sS -X POST "${base_url}/api/v1/tasks" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "'"${MODE}"'",
    "users": ["elonmusk", "naval"],
    "note": "x402 flow: N+mode → quote → pay → xc_live → create task"
  }' | tee /tmp/xcatch_task_create.json

### Step 6 — Get task status (/api/v1/tasks/{task_id})
TASK_ID="<<<TASK_ID_HERE>>>"

curl -sS "${base_url}/api/v1/tasks/${TASK_ID}" \
  -H "Authorization: Bearer ${API_KEY}" | tee /tmp/x402_task_status.json

### Step 7 — Get result download URL (/api/v1/tasks/{task_id}/download)
curl -sS "${base_url}/api/v1/tasks/${TASK_ID}/download" \
  -H "Authorization: Bearer ${API_KEY}" | tee /tmp/x402_download_url.json

### Step 8 — Download the results
DOWNLOAD_URL="<<<DOWNLOAD_URL_HERE>>>"

curl -sS -O "${DOWNLOAD_URL}" | tee /tmp/x402_results_downloaded.json

## Delivery checklist (must include in final reply)
  - N, MODE, points_buy   
  - quote payment details (CHAIN, payTo, amount, expires)  
  - xc_live_* (tell user to save it)  
  - /me verification (username + points)  
  - /tasks result (task id / status)  
  - /download result URL  
  - Results file downloaded
