# Xcatcher curl examples (MCP + x402)

This folder provides a **single end-to-end bash script** that proves the full flow works:

1) Call MCP `create_crawl_task`
2) If points are insufficient, the MCP call returns **PAYMENT_REQUIRED** (402-style)
3) Decode the returned `payment_required_b64` to get a `quote_id` and payment details (**payTo**, amount)
4) Pay via **x402** on **Base or Solana** (you provide the txHash / signature after paying)
5) Call REST `/api/v1/x402/topup` with `PAYMENT-SIGNATURE` to credit your API key
6) Retry `create_crawl_task` with the **same `idempotency_key`** (idempotent retry)
7) Poll `get_task_status` until `has_result=true`
8) Fetch `get_result_download_url` and download the XLSX output

Docs:
- https://xcatcher.top/docs

## Important notes

- **payTo is quote-specific and returned dynamically**, so txHash/signature **cannot** be prepared in advance.
  The correct sequence is: *get quote -> pay to payTo -> paste txHash/signature -> topup*.
- **Minimum top-up is 0.50 USDC** (Base/Solana). Send at least 0.50 USDC even if the quoted amount is lower.

## Prerequisites

- `bash`, `curl`, `jq`, `base64`
- A valid API key: `xc_live_...`

## Quickstart

```bash
cd curl
cp env.example .env
# Edit .env and set API_KEY=xc_live_...
bash mcp_x402_e2e.sh
Non-interactive (CI) usage
If you want to run without prompts, pay first and then provide proof via env vars:

Base:

bash
NETWORK=base BASE_TXHASH=0x... IDEM=curl402-fixed bash mcp_x402_e2e.sh
Solana:

bash
NETWORK=solana SOL_SIGNATURE=... IDEM=curl402-fixed bash mcp_x402_e2e.sh
Tip:

Keep IDEM stable if you re-run after payment, so the retry is idempotent.