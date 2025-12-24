# Xcatcher curl examples (MCP + x402)

This folder provides a **single end-to-end bash script** that proves the full flow works:

1) Call MCP `create_crawl_task`  
2) If points are insufficient, the MCP call returns **402 / PAYMENT_REQUIRED**  
3) Decode the returned `payment_required_b64` to get a `quote_id` and payment details  
4) Pay via **x402** on **Base or Solana** (you provide the txHash / signature)  
5) Call REST `/api/v1/x402/topup` with `PAYMENT-SIGNATURE` to credit your API key  
6) Retry `create_crawl_task` with the **same `idempotency_key`** (idempotent retry)  
7) Poll `get_task_status` until `has_result=true`  
8) Fetch `get_result_download_url` and download the XLSX output

Docs:
- https://xcatcher.top/docs

## Prerequisites
- `bash`, `curl`, `jq`, `base64`
- A valid API key: `xc_live_...`

## Quickstart
```bash
cd curl
cp env.example .env
# Edit .env and set API_KEY=xc_live_...
bash mcp_x402_e2e.sh
Notes:

The script will auto-load ./.env if present.

If you do not set BASE_TXHASH or SOL_SIGNATURE in .env, the script will prompt you.

Choose network (Base or Solana)
In .env:

NETWORK="base" and set BASE_TXHASH="0x...", OR

NETWORK="solana" and set SOL_SIGNATURE="..."

The payment proof is:

Base: the USDC transfer transaction hash (txHash)

Solana: the USDC transfer signature

makefile
复制代码

## `curl/env.example`

```bash
# Base URL
BASE="https://xcatcher.top"

# Your API key (IMPORTANT: no trailing spaces)
API_KEY="xc_live_xxx"

# normal|deep
MODE="deep"

# Users JSON array (keep the single quotes)
USERS_JSON='["elonmusk","naval","sama","paulg","a16z","POTUS","OpenAI","taylorswift13","BillGates","cz_binance","VitalikButerin"]'

# Optional: stable idempotency key for retries
# IDEM="curl402-fixed-id"

# Choose network: base or solana
NETWORK="base"

# If NETWORK=base, set txhash:
# BASE_TXHASH="0x..."

# If NETWORK=solana, set signature:
# SOL_SIGNATURE="..."