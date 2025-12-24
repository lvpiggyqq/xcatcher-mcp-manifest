## OpenAPI import (REST + MCP proxy)

This repo includes an OpenAPI spec for agent builders (Vertex AI / Gemini integrations, OpenAPI tool callers, etc.).

- Spec file: `openapi/xcatcher.yaml`
- Raw URL (import this):
  - https://raw.githubusercontent.com/lvpiggyqq/xcatcher-mcp-manifest/main/openapi/xcatcher.yaml

### Copy & run (3 quick commands)

1) **Google ADK end-to-end (Remote MCP + x402)**
```bash
python -m venv .venv && source .venv/bin/activate && pip install -r google-adk/requirements.txt
XCAT_BASE="https://xcatcher.top" XCAT_API_KEY="xc_live_xxx" XCAT_MODE="normal" python google-adk/adk_mcp_e2e.py
curl end-to-end (MCP create -> 402 -> topup -> retry -> download)

bash
BASE="https://xcatcher.top" API_KEY="xc_live_xxx" MODE="normal" USERS_JSON='["elonmusk"]' bash curl/mcp_x402_e2e.sh
Quote + Topup only (minimum charge: 0.5 USDC)

bash
BASE="https://xcatcher.top"

# (A) Get a quote (public endpoint)
QUOTE_JSON="$(curl -sS "$BASE/api/v1/x402/quote?points=50")"
echo "$QUOTE_JSON" | jq .
QUOTE_ID="$(echo "$QUOTE_JSON" | jq -r '.quote_id')"

# (B) Pay USDC to the returned payTo address (Base or Solana), then set TXHASH or SIGNATURE.
# Base example:
export API_KEY="xc_live_xxx"
export TXHASH="0xYOUR_BASE_TXHASH"

# Build PAYMENT-SIGNATURE = base64(utf-8 JSON)
PAYMENT_SIGNATURE_B64="$(python - <<'PY'
import os, json, base64
tx=os.environ.get("TXHASH","").strip()
obj={"x402Version":1,"scheme":"exact","network":"eip155:8453","payload":{"txHash":tx}}
print(base64.b64encode(json.dumps(obj,separators=(",",":")).encode()).decode())
PY
)"

# (C) Top up points for this Bearer key
curl -sS -X POST "$BASE/api/v1/x402/topup" \
  -H "Authorization: Bearer $API_KEY" \
  -H "PAYMENT-SIGNATURE: $PAYMENT_SIGNATURE_B64" \
  -H "Content-Type: application/json" \
  -d "{\"quote_id\":\"$QUOTE_ID\"}" | jq .
See also:

google-adk/README.md

curl/README.md

Official docs: https://xcatcher.top/docs