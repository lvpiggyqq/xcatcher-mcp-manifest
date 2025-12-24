#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end ADK example for Xcatcher Remote MCP (Streamable HTTP):

tools/list -> create_crawl_task -> (PAYMENT_REQUIRED) -> x402_topup -> retry create
-> poll get_task_status -> get_result_download_url -> download xlsx

Required Env:
  export XCAT_BASE="https://xcatcher.top"
  export XCAT_API_KEY="xc_live_...."

Optional:
  export XCAT_MODE="normal"                      # normal|deep (default: normal, faster)
  export XCAT_USERS="elonmusk,naval,..."         # comma-separated
  export XCAT_IDEMPOTENCY_KEY="your-idem-key"    # stable for retries

  export X402_NETWORK="base"                     # base|solana (default: base)
  export X402_TXHASH="0x..."                     # provide AFTER you pay (Base)
  export X402_SIGNATURE="..."                    # provide AFTER you pay (Solana)

Notes:
  - payTo is quote-specific and returned dynamically; txHash/signature cannot be prepared in advance.
  - Minimum top-up is 0.50 USDC (Base/Solana). Send at least 0.50 USDC.

Output:
  Downloads result to ./task_<task_id>.xlsx
"""

import asyncio
import base64
import inspect
import json
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ---- ADK imports (compat) ----
try:
    from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
except Exception:
    from google.adk.tools.mcp_tool import MCPToolset as McpToolset  # type: ignore
    from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams  # type: ignore


MIN_TOPUP_USDC = "0.50"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


async def _maybe_await(x: Any) -> Any:
    return await x if inspect.isawaitable(x) else x


def _b64json(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _try_parse_json(s: str) -> Optional[Any]:
    try:
        return json.loads(s)
    except Exception:
        return None


def _to_plain(obj: Any) -> Any:
    """Best-effort convert ADK/MCP objects to plain Python types."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool, list, dict)):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return dict(obj.__dict__)
        except Exception:
            pass
    return obj


def _extract_tool_output(payload: Any) -> Any:
    """
    Normalize outputs from ADK McpTool calls.
    Common shapes:
      - dict already containing {"ok": ...}
      - dict with {"structuredContent": {"result": {...}}}
      - dict with {"content":[{"type":"text","text":"{...json...}"}]}
      - raw string
    """
    payload = _to_plain(payload)

    if isinstance(payload, dict):
        if "ok" in payload and ("error" in payload or "task_id" in payload or "download_url" in payload):
            return payload

        sc = payload.get("structuredContent")
        if isinstance(sc, dict):
            if "ok" in sc:
                return sc
            if isinstance(sc.get("result"), dict) and "ok" in sc["result"]:
                return sc["result"]

        content = payload.get("content")
        if isinstance(content, list) and content:
            first = _to_plain(content[0])
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                parsed = _try_parse_json(first["text"])
                return parsed if parsed is not None else first["text"]

        return payload

    if isinstance(payload, list) and payload:
        first = _to_plain(payload[0])
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            parsed = _try_parse_json(first["text"])
            return parsed if parsed is not None else first["text"]
        return payload

    if isinstance(payload, str):
        parsed = _try_parse_json(payload)
        return parsed if parsed is not None else payload

    return payload


async def _get_tools_compat(toolset: Any) -> List[Any]:
    if hasattr(toolset, "get_tools_async"):
        return await _maybe_await(toolset.get_tools_async())
    if hasattr(toolset, "get_tools"):
        return await _maybe_await(toolset.get_tools())
    if hasattr(toolset, "tools"):
        return await _maybe_await(getattr(toolset, "tools"))
    raise AttributeError("McpToolset has no get_tools_async/get_tools/tools on this ADK version")


async def _close_toolset_compat(toolset: Any) -> None:
    for m in ("aclose", "close"):
        if hasattr(toolset, m):
            try:
                await _maybe_await(getattr(toolset, m)())
            except Exception as e:
                print(f"Warning: toolset.{m} failed: {e}", file=sys.stderr)
            return


async def _call_mcp_tool(tool_obj: Any, args: Dict[str, Any]) -> Any:
    if hasattr(tool_obj, "run_async"):
        fn = tool_obj.run_async
        try:
            return await fn(args=args, tool_context=None)
        except TypeError:
            pass
        try:
            return await fn(args=args)
        except TypeError:
            pass
        try:
            return await fn(args)
        except TypeError:
            pass
        return await fn(**args)

    if callable(tool_obj):
        res = tool_obj(args)
        return await _maybe_await(res)

    raise TypeError(f"Tool object is not runnable: {tool_obj}")


def _decode_payment_required_b64(b64: str) -> Dict[str, Any]:
    raw = base64.b64decode(b64).decode("utf-8", errors="replace")
    obj = _try_parse_json(raw)
    if isinstance(obj, dict):
        return obj
    return {"_raw": raw}


def _pick_quote_from_payment_required(pr: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    quote_id = (pr.get("quote_id") or "").strip()
    accepts = pr.get("accepts") if isinstance(pr.get("accepts"), dict) else {}
    if not quote_id:
        raise ValueError("payment_required missing quote_id")
    return quote_id, accepts


async def _rest_get_me(base: str, api_key: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base}/api/v1/me",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        try:
            return r.json()
        except Exception:
            return {"_status": r.status_code, "_text": r.text}


async def _download_file(url: str, api_key: str, out_path: str) -> None:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=headers) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                async for chunk in r.aiter_bytes():
                    if chunk:
                        f.write(chunk)


def _default_users() -> List[str]:
    return ["elonmusk", "naval", "balajis", "pmarca", "sama", "a16z"]


async def main() -> int:
    base = _env("XCAT_BASE", "https://xcatcher.top").rstrip("/")
    api_key = _env("XCAT_API_KEY", "")
    if not api_key:
        print("ERROR: missing env XCAT_API_KEY", file=sys.stderr)
        return 2

    mcp_headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Prefer normal mode (faster) for examples
    mode = (_env("XCAT_MODE", "normal").lower() or "normal")
    users_env = _env("XCAT_USERS", "")
    users = [u.strip().lstrip("@") for u in users_env.split(",") if u.strip()] if users_env else _default_users()

    idem_key = _env("XCAT_IDEMPOTENCY_KEY", "") or f"adk-e2e-{uuid.uuid4().hex[:16]}"

    x402_network = (_env("X402_NETWORK", "base").lower() or "base")
    x402_txhash = _env("X402_TXHASH", "")
    x402_sig = _env("X402_SIGNATURE", "")

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=f"{base}/mcp", headers=mcp_headers),
        tool_filter=[
            "create_crawl_task",
            "x402_topup",
            "get_task_status",
            "get_result_download_url",
            "cancel_task",
        ],
    )

    try:
        print("\n== 0) Notes ==")
        print(f" - Default mode: {mode} (faster for examples)")
        print(" - payTo is quote-specific and returned dynamically; txHash/signature is available only AFTER you pay.")
        print(f" - Minimum top-up: {MIN_TOPUP_USDC} USDC\n")

        print("== 1) tools/list (via ADK McpToolset) ==")
        tools = await _get_tools_compat(toolset)

        tool_map: Dict[str, Any] = {}
        for t in tools:
            name = getattr(t, "name", None)
            if not name and isinstance(_to_plain(t), dict):
                name = _to_plain(t).get("name")
            if name:
                tool_map[str(name)] = t

        if not tool_map:
            print("ERROR: tool list empty; ADK returned no tools", file=sys.stderr)
            return 11

        for name in sorted(tool_map.keys()):
            print(f" - {name}")

        def must(name: str) -> Any:
            if name not in tool_map:
                raise RuntimeError(f"Missing tool: {name}. Available: {sorted(tool_map.keys())}")
            return tool_map[name]

        t_create = must("create_crawl_task")
        t_topup = must("x402_topup")
        t_status = must("get_task_status")
        t_dl = must("get_result_download_url")

        print("\n== 2) (REST) /api/v1/me: check current points ==")
        me = await _rest_get_me(base, api_key)
        print(json.dumps(me, ensure_ascii=False, indent=2))

        print("\n== 3) call create_crawl_task (expect PAYMENT_REQUIRED when points insufficient) ==")
        create_args = {"users": users, "mode": mode, "idempotency_key": idem_key}
        raw1 = await _call_mcp_tool(t_create, create_args)
        out1 = _extract_tool_output(raw1)
        print(json.dumps(out1, ensure_ascii=False, indent=2))

        task_id = None

        if (
            isinstance(out1, dict)
            and (out1.get("ok") is False)
            and isinstance(out1.get("error"), dict)
            and out1["error"].get("code") == "PAYMENT_REQUIRED"
        ):
            details = out1["error"].get("details") if isinstance(out1["error"].get("details"), dict) else {}
            pr_b64 = (details.get("payment_required_b64") or "").strip()
            pr_obj = details.get("payment_required") if isinstance(details.get("payment_required"), dict) else None

            print("\n== 4) decode PAYMENT_REQUIRED ==")
            if not pr_obj:
                if not pr_b64:
                    print("ERROR: missing payment_required_b64/payment_required in response.details", file=sys.stderr)
                    return 3
                pr_obj = _decode_payment_required_b64(pr_b64)

            quote_id, accepts = _pick_quote_from_payment_required(pr_obj)

            # Print a short summary to guide the payment step
            summary = {
                "quote_id": quote_id,
                "expires_in": pr_obj.get("expires_in"),
                "task_cost_points": pr_obj.get("task_cost_points"),
                "balance_points": pr_obj.get("balance_points"),
                "minimum_topup_usdc": MIN_TOPUP_USDC,
                "base": accepts.get("base"),
                "solana": accepts.get("solana"),
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))

            print("\n== 5) choose network + build payment_signature_b64 ==")
            print("Action required: pay USDC to the returned payTo address, then provide txHash/signature.")
            print(f"Minimum top-up: {MIN_TOPUP_USDC} USDC")

            if x402_network not in ("base", "solana"):
                print("ERROR: X402_NETWORK must be base|solana", file=sys.stderr)
                return 4

            if x402_network == "base":
                if not x402_txhash:
                    x402_txhash = input("Enter Base txHash (0x...): ").strip()
                payment_sig_b64 = _b64json({
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": "eip155:8453",
                    "payload": {"txHash": x402_txhash},
                })
            else:
                if not x402_sig:
                    x402_sig = input("Enter Solana signature: ").strip()
                payment_sig_b64 = _b64json({
                    "x402Version": 1,
                    "scheme": "exact",
                    "network": "solana:mainnet",
                    "payload": {"signature": x402_sig},
                })

            print(f"\nquote_id={quote_id}")
            print(f"payment_signature_b64={payment_sig_b64}")

            print("\n== 6) call x402_topup (via MCP tool) ==")
            raw2 = await _call_mcp_tool(t_topup, {"quote_id": quote_id, "payment_signature_b64": payment_sig_b64})
            out2 = _extract_tool_output(raw2)
            print(json.dumps(out2, ensure_ascii=False, indent=2))
            if not (isinstance(out2, dict) and out2.get("ok") is True):
                print("ERROR: x402_topup failed", file=sys.stderr)
                return 5

            print("\n== 7) retry create_crawl_task with SAME idempotency_key ==")
            raw3 = await _call_mcp_tool(t_create, create_args)
            out3 = _extract_tool_output(raw3)
            print(json.dumps(out3, ensure_ascii=False, indent=2))

            if not (isinstance(out3, dict) and out3.get("ok") is True):
                print("ERROR: create_crawl_task still failed after topup", file=sys.stderr)
                return 6

            task_id = out3.get("task_id")

        else:
            if not (isinstance(out1, dict) and out1.get("ok") is True):
                print("ERROR: create_crawl_task failed (not PAYMENT_REQUIRED)", file=sys.stderr)
                return 7
            task_id = out1.get("task_id")

        if not task_id:
            print("ERROR: missing task_id", file=sys.stderr)
            return 8

        print(f"\n== 8) poll get_task_status until has_result=true (task_id={task_id}) ==")
        deadline = time.time() + 900
        last = None
        while time.time() < deadline:
            raw_s = await _call_mcp_tool(t_status, {"task_id": int(task_id)})
            st = _extract_tool_output(raw_s)
            last = st
            print(json.dumps(st, ensure_ascii=False, indent=2))
            if isinstance(st, dict) and st.get("ok") is True and st.get("has_result") is True:
                break
            await asyncio.sleep(5)

        if not (isinstance(last, dict) and last.get("ok") is True and last.get("has_result") is True):
            print("ERROR: timeout waiting for result", file=sys.stderr)
            return 9

        print("\n== 9) get_result_download_url ==")
        raw_d = await _call_mcp_tool(t_dl, {"task_id": int(task_id)})
        dl = _extract_tool_output(raw_d)
        print(json.dumps(dl, ensure_ascii=False, indent=2))

        if not (isinstance(dl, dict) and dl.get("ok") is True and isinstance(dl.get("download_url"), str)):
            print("ERROR: failed to get download_url", file=sys.stderr)
            return 10

        download_url = dl["download_url"]
        out_file = f"task_{task_id}.xlsx"

        print(f"\n== 10) download result file -> {out_file} ==")
        await _download_file(download_url, api_key, out_file)

        print("\nDONE.")
        print(f"task_id={task_id}")
        print(f"download_url={download_url}")
        print(f"saved_file=./{out_file}")
        return 0

    finally:
        await _close_toolset_compat(toolset)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
