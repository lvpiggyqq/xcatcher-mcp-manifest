#!/usr/bin/env python3
"""Convert reviewed TweetClaw exports into Xcatcher users JSON.

Input can be a JSON array, a JSON object with a common rows key, or JSONL.
Output is a deduplicated JSON array of X usernames without leading @.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROWS_KEYS = ("items", "tweets", "results", "data", "rows")
HANDLE_KEYS = (
    "authorUsername",
    "author_username",
    "screen_name",
    "username",
    "userName",
    "handle",
)
RESERVED_X_PATHS = {
    "compose",
    "explore",
    "hashtag",
    "home",
    "i",
    "intent",
    "login",
    "logout",
    "messages",
    "notifications",
    "search",
    "settings",
    "share",
}
HANDLE_RE = r"[A-Za-z0-9_]{1,15}"


def load_rows(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ROWS_KEYS:
            rows = parsed.get(key)
            if isinstance(rows, list):
                return rows
        return [parsed]
    return []


def normalize_handle(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.netloc.lower().removeprefix("www.") in {"x.com", "twitter.com"}:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return None
        first_segment = segments[0]
        if first_segment.lower() in RESERVED_X_PATHS:
            return None
        value = first_segment
    value = value.removeprefix("@")
    if re.fullmatch(HANDLE_RE, value):
        return value
    return None


def extract_handle(row: Any) -> str | None:
    if not isinstance(row, dict):
        return None
    for key in HANDLE_KEYS:
        handle = normalize_handle(row.get(key))
        if handle:
            return handle
    for key in ("author", "user", "profile"):
        nested = row.get(key)
        if isinstance(nested, dict):
            handle = extract_handle(nested)
            if handle:
                return handle
    for key in ("url", "tweetUrl", "tweet_url", "profileUrl", "profile_url"):
        handle = normalize_handle(row.get(key))
        if handle:
            return handle
    return None


def collect_users(rows: list[Any]) -> list[str]:
    seen: set[str] = set()
    users: list[str] = []
    for row in rows:
        handle = extract_handle(row)
        if handle and handle.lower() not in seen:
            seen.add(handle.lower())
            users.append(handle)
    return users


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Xcatcher users JSON from reviewed TweetClaw exports.",
    )
    parser.add_argument("export", type=Path, help="TweetClaw JSON or JSONL export")
    args = parser.parse_args()

    json.dump(collect_users(load_rows(args.export)), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
