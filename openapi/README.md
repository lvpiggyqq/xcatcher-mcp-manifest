# Xcatcher OpenAPI (REST + MCP proxy)

Why this exists:
Many agent builders (including Vertex AI / Gemini integrations) can import OpenAPI specs directly.
This spec covers:
- REST endpoints (/api/v1/me, /api/v1/x402/quote, /api/v1/x402/topup, /api/v1/tasks/{id}/download)
- An optional generic MCP proxy endpoint (POST /mcp/) for JSON-RPC calls

Notes:
- Using dedicated REST operations for task tools is more reliable than asking the model to craft JSON-RPC.
- If you add a REST facade for MCP tools, update the spec with strongly-typed endpoints.
