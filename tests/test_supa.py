import asyncio
import json
import os
import sys
import unittest

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import supa


class Fake:
    def __init__(self, status=200, body=None, headers=None):
        self.calls = []
        self.status, self.body, self.headers = status, body if body is not None else [], headers or {}

    def __call__(self, request):
        self.calls.append(request)
        return httpx.Response(self.status, json=self.body, headers=self.headers)


def run(coro):
    return asyncio.run(coro)


class SupaTests(unittest.TestCase):
    def setUp(self):
        os.environ["SUPABASE_URL"] = "https://example.supabase.co/"
        os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
        self.fake = Fake()
        supa._transport = httpx.MockTransport(self.fake)

    def tearDown(self):
        supa._transport = None

    def test_missing_env(self):
        del os.environ["SUPABASE_URL"]
        with self.assertRaises(RuntimeError):
            run(supa.user_exists(1))

    def test_auth_headers_and_url(self):
        run(supa.user_exists(5))
        req = self.fake.calls[0]
        self.assertEqual(req.url.path, "/rest/v1/bot_users")
        self.assertEqual(req.headers["apikey"], "test-key")
        self.assertEqual(req.headers["authorization"], "Bearer test-key")
        self.assertEqual(req.url.params["user_id"], "eq.5")

    def test_user_exists(self):
        self.fake.body = [{"user_id": 5}]
        self.assertTrue(run(supa.user_exists(5)))
        self.fake.body = []
        self.assertFalse(run(supa.user_exists(5)))

    def test_touch_user_ignores_duplicates(self):
        run(supa.touch_user(7))
        req = self.fake.calls[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.url.params["on_conflict"], "user_id")
        self.assertIn("ignore-duplicates", req.headers["prefer"])
        self.assertEqual(json.loads(req.content), [{"user_id": 7}])

    def test_save_recording(self):
        run(supa.save_recording("t", "fiqh", None, "F1"))
        body = json.loads(self.fake.calls[0].content)
        self.assertEqual(body, [{"title": "t", "category": "fiqh", "session_no": None, "file_id": "F1"}])

    def test_category_page_total_and_order(self):
        self.fake.body = [{"id": 1, "title": "a"}]
        self.fake.headers = {"content-range": "0-9/57"}
        rows, total = run(supa.category_page("muslim", 2, 10))
        self.assertEqual((len(rows), total), (1, 57))
        p = self.fake.calls[0].url.params
        self.assertEqual(p["category"], "eq.muslim")
        self.assertEqual(p["offset"], "20")
        self.assertEqual(p["limit"], "10")
        self.assertEqual(p["order"], "session_no.asc.nullsfirst,id.asc")

    def test_empty_total(self):
        self.fake.headers = {"content-range": "*/0"}
        self.assertEqual(run(supa.category_page("old", 0, 10))[1], 0)

    def test_search_escapes_wildcards(self):
        run(supa.search_title("50%_a*"))
        self.assertEqual(self.fake.calls[0].url.params["title"], "ilike.*50\\%\\_a*")

    def test_get_recording(self):
        self.assertIsNone(run(supa.get_recording(3)))
        self.fake.body = [{"title": "x", "file_id": "f"}]
        self.assertEqual(run(supa.get_recording(3))["file_id"], "f")

    def test_error_hides_key(self):
        self.fake.status, self.fake.body = 401, {"message": "bad"}
        with self.assertRaises(RuntimeError) as cm:
            run(supa.recordings_latest(5))
        self.assertNotIn("test-key", str(cm.exception))
        self.assertIn("401", str(cm.exception))

    def test_count(self):
        self.fake.headers = {"content-range": "0-0/42"}
        self.assertEqual(run(supa.count("recordings")), 42)


if __name__ == "__main__":
    unittest.main()
