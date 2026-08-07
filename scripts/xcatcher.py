#!/usr/bin/env python3
"""Dependency-free REST fallback for the Xcatcher Agent Skill."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE = "https://xcatcher.top"


def api_key(args: argparse.Namespace) -> str:
    value = (getattr(args, "api_key", None) or os.getenv("XCATCHER_API_KEY") or "").strip()
    if not value:
        raise SystemExit("XCATCHER_API_KEY is required for this command")
    return value


def request(
    base: str,
    method: str,
    path: str,
    *,
    key: str = "",
    body: dict[str, Any] | None = None,
    payment_signature: str = "",
) -> tuple[int, dict[str, Any], bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    headers = {"Accept": "application/json", "User-Agent": "xcatcher-agent-skill/3.0"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if payment_signature:
        headers["PAYMENT-SIGNATURE"] = payment_signature
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            status = response.status
            response_headers = {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        response_headers = {k.lower(): v for k, v in exc.headers.items()}
    try:
        payload = json.loads(raw) if raw else {}
    except (ValueError, UnicodeDecodeError):
        payload = {}
    return status, payload, raw, response_headers


def emit(
    status: int,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    *,
    exit_on_error: bool = True,
) -> None:
    output: dict[str, Any] = {"http_status": status, "body": payload}
    if headers:
        retry_after = headers.get("retry-after")
        payment_required = headers.get("payment-required")
        payment_response = headers.get("payment-response")
        if retry_after:
            output["retry_after"] = retry_after
        if payment_required:
            try:
                output["payment_required"] = json.loads(base64.b64decode(payment_required))
            except Exception:
                output["payment_required_b64"] = payment_required
        if payment_response:
            try:
                output["payment_response"] = json.loads(base64.b64decode(payment_response))
            except Exception:
                output["payment_response_b64"] = payment_response
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if status >= 400 and exit_on_error:
        raise SystemExit(1)


def stable_idempotency(mode: str, users: list[str]) -> str:
    canonical = json.dumps({"mode": mode, "users": users}, separators=(",", ":"), ensure_ascii=True)
    return "xcatcher-" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


def normalize_users(values: list[str]) -> list[str]:
    seen: set[str] = set()
    users: list[str] = []
    for raw in values:
        value = raw.strip()
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc.lower().removeprefix("www.") in {"x.com", "twitter.com"}:
            value = parsed.path.strip("/").split("/", 1)[0]
        value = value.lstrip("@").strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            users.append(value)
    if not users:
        raise SystemExit("at least one X handle is required")
    return users


def main() -> None:
    parser = argparse.ArgumentParser(description="Xcatcher REST fallback client")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--api-key", help="defaults to XCATCHER_API_KEY")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health")
    sub.add_parser("capabilities")
    sub.add_parser("tools")

    register = sub.add_parser("register")
    register.add_argument("username")
    register.add_argument("password")

    login = sub.add_parser("login")
    login.add_argument("username")
    login.add_argument("password")

    sub.add_parser("me")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.add_argument("--before-id", type=int)

    quote = sub.add_parser("quote")
    quote.add_argument("points", type=int)

    create = sub.add_parser("create")
    create.add_argument("users", nargs="+")
    create.add_argument("--mode", choices=("normal", "deep"), default="normal")
    create.add_argument("--idempotency-key")

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("task_id", type=int)

    results = sub.add_parser("results")
    results.add_argument("task_id", type=int)
    results.add_argument("--limit", type=int, default=50)
    results.add_argument("--offset", type=int, default=0)

    wait = sub.add_parser("wait")
    wait.add_argument("task_id", type=int)
    wait.add_argument("--timeout", type=int, default=120)
    wait.add_argument("--interval", type=int, default=5)

    topup = sub.add_parser("topup")
    topup.add_argument("quote_id")
    topup.add_argument("payment_signature_b64")

    buy = sub.add_parser("buy-points")
    buy.add_argument("quote_id")
    buy.add_argument("payment_signature_b64")

    direct_quote = sub.add_parser("direct-quote")
    direct_quote.add_argument("users", nargs="+")
    direct_quote.add_argument("--mode", choices=("normal", "deep"), default="normal")

    direct_submit = sub.add_parser("direct-submit")
    direct_submit.add_argument("payment_signature_b64")
    direct_submit.add_argument("users", nargs="+")
    direct_submit.add_argument("--mode", choices=("normal", "deep"), default="normal")

    direct_status = sub.add_parser("direct-status")
    direct_status.add_argument("task_id", type=int)
    direct_status.add_argument("task_token")

    direct_results = sub.add_parser("direct-results")
    direct_results.add_argument("task_id", type=int)
    direct_results.add_argument("task_token")
    direct_results.add_argument("--limit", type=int, default=50)
    direct_results.add_argument("--offset", type=int, default=0)

    direct_download = sub.add_parser("direct-download")
    direct_download.add_argument("task_id", type=int)
    direct_download.add_argument("task_token")
    direct_download.add_argument("--output", type=Path)

    download = sub.add_parser("download")
    download.add_argument("task_id", type=int)
    download.add_argument("--output", type=Path)

    args = parser.parse_args()
    base = args.base.rstrip("/")

    if args.command == "health":
        status, payload, raw, headers = request(base, "GET", "/mcp/health")
        if not payload:
            payload = {"status": raw.decode("utf-8", "replace").strip()}
        emit(status, payload, headers)
    elif args.command == "capabilities":
        status, payload, _, headers = request(base, "GET", "/api/v1/capabilities")
        emit(status, payload, headers)
    elif args.command == "tools":
        status, payload, _, headers = request(
            base,
            "POST",
            "/mcp/",
            body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        emit(status, payload, headers)
    elif args.command == "register":
        status, payload, _, headers = request(
            base, "POST", "/api/v1/auth/register", body={"username": args.username, "password": args.password}
        )
        emit(status, payload, headers)
    elif args.command == "login":
        status, payload, _, headers = request(
            base, "POST", "/api/v1/auth/login", body={"username": args.username, "password": args.password}
        )
        emit(status, payload, headers)
    elif args.command == "me":
        status, payload, _, headers = request(base, "GET", "/api/v1/me", key=api_key(args))
        emit(status, payload, headers)
    elif args.command == "list":
        query = urllib.parse.urlencode({
            "limit": max(1, min(100, args.limit)),
            **({"before_id": args.before_id} if args.before_id else {}),
        })
        status, payload, _, headers = request(base, "GET", f"/api/v1/tasks?{query}", key=api_key(args))
        emit(status, payload, headers)
    elif args.command == "quote":
        status, payload, _, headers = request(base, "GET", f"/api/v1/x402/quote?points={args.points}")
        emit(status, payload, headers)
    elif args.command == "create":
        users = normalize_users(args.users)
        idem = args.idempotency_key or stable_idempotency(args.mode, users)
        status, payload, _, headers = request(
            base,
            "POST",
            "/api/v1/tasks",
            key=api_key(args),
            body={"mode": args.mode, "users": users, "idempotency_key": idem},
        )
        emit(status, payload, headers)
    elif args.command == "status":
        status, payload, _, headers = request(base, "GET", f"/api/v1/tasks/{args.task_id}", key=api_key(args))
        emit(status, payload, headers)
    elif args.command == "results":
        query = urllib.parse.urlencode({"limit": max(1, min(200, args.limit)), "offset": max(0, args.offset)})
        status, payload, _, headers = request(
            base, "GET", f"/api/v1/tasks/{args.task_id}/results?{query}", key=api_key(args)
        )
        emit(status, payload, headers)
    elif args.command == "wait":
        deadline = time.monotonic() + max(1, args.timeout)
        while True:
            status, payload, _, headers = request(base, "GET", f"/api/v1/tasks/{args.task_id}", key=api_key(args))
            if status >= 400 or payload.get("status") in {"done", "failed", "cancelled"}:
                emit(status, payload, headers)
                return
            if time.monotonic() >= deadline:
                payload["wait_timed_out"] = True
                emit(status, payload, headers)
                return
            time.sleep(max(2, args.interval))
    elif args.command == "topup":
        status, payload, _, headers = request(
            base,
            "POST",
            "/api/v1/x402/topup",
            key=api_key(args),
            body={"quote_id": args.quote_id},
            payment_signature=args.payment_signature_b64,
        )
        emit(status, payload, headers)
    elif args.command == "buy-points":
        status, payload, _, headers = request(
            base,
            "POST",
            "/api/v1/x402/buy_points",
            body={"quote_id": args.quote_id},
            payment_signature=args.payment_signature_b64,
        )
        emit(status, payload, headers)
    elif args.command == "direct-quote":
        users = normalize_users(args.users)
        status, payload, _, headers = request(
            base, "POST", "/api/v1/x402/crawl", body={"users": users, "mode": args.mode}
        )
        # HTTP 402 is the expected successful challenge output for this command.
        emit(status, payload, headers, exit_on_error=status != 402)
    elif args.command == "direct-submit":
        users = normalize_users(args.users)
        status, payload, _, headers = request(
            base,
            "POST",
            "/api/v1/x402/crawl",
            body={"users": users, "mode": args.mode},
            payment_signature=args.payment_signature_b64,
        )
        emit(status, payload, headers)
    elif args.command == "direct-status":
        status, payload, _, headers = request(
            base, "GET", f"/api/v1/x402/tasks/{args.task_id}", key=args.task_token
        )
        emit(status, payload, headers)
    elif args.command == "direct-results":
        query = urllib.parse.urlencode({"limit": max(1, min(200, args.limit)), "offset": max(0, args.offset)})
        status, payload, _, headers = request(
            base, "GET", f"/api/v1/x402/tasks/{args.task_id}/results?{query}", key=args.task_token
        )
        emit(status, payload, headers)
    elif args.command == "direct-download":
        output = args.output or Path(f"task_{args.task_id}.xlsx")
        status, payload, raw, headers = request(
            base, "GET", f"/api/v1/x402/tasks/{args.task_id}/download", key=args.task_token
        )
        if status >= 400:
            emit(status, payload, headers)
        output.write_bytes(raw)
        print(json.dumps({"http_status": status, "saved": str(output), "bytes": len(raw)}, indent=2))
    elif args.command == "download":
        output = args.output or Path(f"task_{args.task_id}.xlsx")
        status, payload, raw, headers = request(
            base, "GET", f"/api/v1/tasks/{args.task_id}/download", key=api_key(args)
        )
        if status >= 400:
            emit(status, payload, headers)
        output.write_bytes(raw)
        print(json.dumps({"http_status": status, "saved": str(output), "bytes": len(raw)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(json.dumps({"error": "network_error", "message": str(exc.reason)}), file=sys.stderr)
        raise SystemExit(2)
