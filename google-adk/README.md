# Xcatcher Google ADK examples (Remote MCP + x402)

This folder shows how to connect **Google ADK** to a **Remote MCP server (Streamable HTTP)** and run an end-to-end workflow:

- `tools/list`
- `create_crawl_task`
- If points are insufficient: `PAYMENT_REQUIRED` -> decode quote -> `x402_topup`
- Retry `create_crawl_task` with the **same** `idempotency_key`
- Poll `get_task_status` until `has_result=true`
- `get_result_download_url`
- Download the XLSX file

Docs:
- https://xcatcher.top/docs

## Important notes

- **payTo is quote-specific and returned dynamically**, so txHash/signature **cannot** be prepared in advance.
  The correct sequence is: *get quote -> pay to payTo -> paste txHash/signature -> topup*.
- **Minimum top-up is 0.50 USDC** (Base/Solana). Send at least 0.50 USDC even if the quoted amount is lower.
- Examples default to **mode=normal** because it's faster.

## Setup

```bash
cd google-adk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Environment variables
Required:

bash
export XCAT_BASE="https://xcatcher.top"
export XCAT_API_KEY="xc_live_xxx"
Optional:

bash
export XCAT_MODE="normal"                      # normal|deep (default: normal)
export XCAT_USERS="elonmusk,naval,a16z"        # comma-separated
export XCAT_IDEMPOTENCY_KEY="fixed-idem-key"   # stable for retries

export X402_NETWORK="base"                     # base|solana (default: base)
export X402_TXHASH="0x..."                     # provide AFTER you pay (Base)
export X402_SIGNATURE="..."                    # provide AFTER you pay (Solana)
Run
bash
python minimal_list_tools.py
python adk_mcp_e2e.py
Notes
If you do not set X402_TXHASH / X402_SIGNATURE, the script will prompt you.

The code includes compatibility fallbacks for different ADK versions