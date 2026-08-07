# Xcatcher x402 payments

Use the accountless direct crawl for new wallet-based integrations. It implements the standard x402 v2 HTTP flow on Base and does not require an Xcatcher account.

## Safety invariants

- Obtain approval for the exact live amount, USDC contract, Base network, and `payTo` unless a user policy already authorizes all of them.
- Never request, expose, or store seed phrases/private keys. Use a wallet or x402 client that signs internally.
- Keep payment signatures and task tokens out of prompt-visible arguments, command-line history, logs, and ordinary files. Use the wallet/client's credential channel or the agent host's secret store; stop before submission if neither is available.
- A challenge is bound to normalized `users`, `mode`, resource URL, and `quoteId`. Do not change any of them between challenge and submission.
- Quotes expire. Never reuse cached payment terms or a signature for a different request.
- If settlement response is uncertain, retry the identical signed request. Do not create a new quote or pay again until the original receipt state is known.

## Standard direct-crawl exchange

First request:

```http
POST /api/v1/x402/crawl
Content-Type: application/json

{"users":["openai","naval"],"mode":"normal"}
```

The server responds `402` with a Base64-encoded `PAYMENT-REQUIRED` header and equivalent JSON body:

```json
{
  "x402Version": 2,
  "resource": {
    "url": "https://xcatcher.top/api/v1/x402/crawl",
    "description": "Fetch recent public X posts for named handles",
    "mimeType": "application/json"
  },
  "accepts": [{
    "scheme": "exact",
    "network": "eip155:8453",
    "amount": "...",
    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "payTo": "...",
    "maxTimeoutSeconds": 120,
    "extra": {
      "assetTransferMethod": "eip3009",
      "name": "USD Coin",
      "version": "2",
      "quoteId": "q_..."
    }
  }],
  "extensions": {
    "bazaar": {
      "info": {
        "input": {
          "type": "http",
          "method": "POST",
          "bodyType": "json",
          "body": {"users": ["openai"], "mode": "normal"}
        }
      },
      "schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "...": "full live schema"}
    }
  }
}
```

The example abbreviates the Bazaar output and JSON Schema. Wallet clients must copy the complete live `PAYMENT-REQUIRED` value unchanged rather than reconstructing its `extensions` field. Bazaar-aware clients can use this metadata to understand the POST body and result shape; catalog inclusion still depends on settlement through a facilitator that supports Bazaar indexing.

An x402 v2 wallet connector selects the exact accepted requirement and signs internally. Xcatcher verifies the EIP-712 authorization and settles USDC with `transferWithAuthorization`; the wallet never sends a private key to Xcatcher, and the model must not receive the payment proof.

Have the approved x402 connector retry the exact HTTP request without copying any credential through chat. Success is `201` with:

- `PAYMENT-RESPONSE`: Base64 settlement result including transaction/network/payer
- `task.task_id`: async crawl task
- `task_token`: task-scoped Bearer credential, reusable for that task until its seven-day expiry; keep it secret
- `access_expires_at`: seven-day access expiry

Put the token in a host secret store, then inject it only for `/api/v1/x402/tasks/{task_id}` and its `/results` or `/download` children. Do not place the token in a prompt, command-line argument, or generated report.

## Account top-up compatibility

`get_x402_quote` and `x402_topup` remain for existing point accounts and may advertise compatibility requirements on Base or Solana. Follow the live requirement returned by that endpoint; do not apply the direct-crawl v2 payload shape to a compatibility quote. Prefer the direct v2 crawl for new pay-per-use integrations.
