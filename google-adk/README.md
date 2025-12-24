# Xcatcher Google ADK examples (Remote MCP + x402)

This folder shows how to connect **Google ADK** to a **Remote MCP server (Streamable HTTP)** and run an end-to-end workflow:

- `tools/list`
- `create_crawl_task`
- If points are insufficient: `PAYMENT_REQUIRED` (402) -> decode quote -> `x402_topup`
- Retry `create_crawl_task` with the **same** `idempotency_key`
- Poll `get_task_status` until `has_result=true`
- `get_result_download_url`
- Download the XLSX file

Docs:
- https://xcatcher.top/docs

## Setup

```bash
cd google-adk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
Environment variables
Required:

bash
复制代码
export XCAT_BASE="https://xcatcher.top"
export XCAT_API_KEY="xc_live_xxx"
Optional:

bash
复制代码
export XCAT_MODE="deep"                         # normal|deep
export XCAT_USERS="elonmusk,naval,a16z"         # comma-separated
export XCAT_IDEMPOTENCY_KEY="fixed-idem-key"    # stable for retries

export X402_NETWORK="base"                      # base|solana (default: base)
export X402_TXHASH="0x..."                      # if base
export X402_SIGNATURE="..."                     # if solana
Run
bash
复制代码
python minimal_list_tools.py
python adk_mcp_e2e.py
Notes:

If you do not set X402_TXHASH / X402_SIGNATURE, the script will prompt you.

The code includes compatibility fallbacks for different ADK versions.

shell
 

## `google-adk/requirements.txt`

```txt
httpx>=0.27.0
google-adk