import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import headers as h  # noqa: E402
import unsubscriber as u  # noqa: E402
from demo_data import demo_messages  # noqa: E402


class Boom:
    """Stands in for requests/smtp: any use fails the test."""
    def post(self, *a, **k):
        raise AssertionError("network used")

    def send(self, *a, **k):
        raise AssertionError("smtp used")

    def close(self):
        pass


class Unsubscribe(unittest.TestCase):
    def setUp(self):
        self.senders = h.aggregate(demo_messages())

    def test_dry_run_touches_no_network_and_respects_allowlist(self):
        res = u.process(self.senders, dry_run=True, allowlist={"news@trusted-shop.example"},
                        session=Boom(), smtp=Boom())
        by = {r.address: r for r in res}
        self.assertEqual(by["news@trusted-shop.example"].status, u.SKIPPED)
        self.assertEqual(by["deals@shop-one.example"].status, u.DRY_RUN)
        self.assertEqual(by["news@weekly-digest.example"].status, u.DRY_RUN)
        link = by["offers@travel.example"]
        self.assertEqual((link.status, link.link), (u.MANUAL, "https://travel.example/preferences?u=42"))

    def test_domain_allowlist(self):
        self.assertTrue(u.is_allowlisted("x@Trusted-Shop.example", {"@trusted-shop.example"}))
        self.assertFalse(u.is_allowlisted("x@other.example", {"@trusted-shop.example"}))

    def test_live_one_click_posts_exact_body_without_redirects(self):
        calls = []

        class Resp:
            status_code, headers = 200, {}

        class Sess:
            def post(self, url, **kw):
                calls.append((url, kw))
                return Resp()

        s = [x for x in self.senders if x.address == "deals@shop-one.example"]
        orig = u._check_public_https
        u._check_public_https = lambda url: None  # no DNS in tests
        try:
            res = u.process(s, dry_run=False, allowlist=set(), session=Sess(), smtp=Boom())
        finally:
            u._check_public_https = orig
        self.assertEqual(res[0].status, u.SUCCESS)
        self.assertEqual(calls[0][1]["data"], "List-Unsubscribe=One-Click")
        self.assertFalse(calls[0][1]["allow_redirects"])

    def test_private_host_refused(self):
        with self.assertRaises(ValueError):
            u._check_public_https("https://127.0.0.1/unsub")

    def test_log_written(self):
        res = [u.Result("a@x.example", h.MAILTO, u.DRY_RUN, "d"), u.Result("=b@x", h.NONE, u.MANUAL)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "log.csv")
            u.append_log(p, res, True)
            u.append_log(p, res, True)
            with open(p, encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        self.assertEqual(len(rows), 5)  # one header + 2 x 2
        self.assertEqual(rows[0][2], "sender")
        self.assertEqual(rows[2][2], "'=b@x")


if __name__ == "__main__":
    unittest.main()
