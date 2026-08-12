import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from tweetclaw_to_users import collect_users, load_rows, normalize_handle  # noqa: E402


class TweetClawToUsersTests(unittest.TestCase):
    def test_loads_nested_json_and_deduplicates_handles(self) -> None:
        payload = {
            "results": [
                {"authorUsername": "OpenAI"},
                {"author": {"username": "openai"}},
                {"tweetUrl": "https://x.com/naval/status/123"},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            path = Path(handle.name)

        try:
            self.assertEqual(collect_users(load_rows(path)), ["OpenAI", "naval"])
        finally:
            path.unlink()

    def test_loads_jsonl_rows(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as handle:
            handle.write(json.dumps({"user": {"screen_name": "alice"}}) + "\n")
            handle.write(json.dumps({"profileUrl": "https://twitter.com/bob"}) + "\n")
            path = Path(handle.name)

        try:
            self.assertEqual(collect_users(load_rows(path)), ["alice", "bob"])
        finally:
            path.unlink()

    def test_rejects_reserved_and_non_profile_urls(self) -> None:
        self.assertIsNone(normalize_handle("https://x.com/i/web/status/123"))
        self.assertIsNone(normalize_handle("https://x.com/search?q=OpenAI"))
        self.assertIsNone(normalize_handle("https://example.com/OpenAI"))

    def test_accepts_profile_urls_and_handles(self) -> None:
        self.assertEqual(normalize_handle("@OpenAI"), "OpenAI")
        self.assertEqual(normalize_handle("https://www.x.com/OpenAI"), "OpenAI")


if __name__ == "__main__":
    unittest.main()
