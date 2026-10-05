import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import headers as h  # noqa: E402

RAW = (
    b'From: =?UTF-8?B?Q2Fmw6k=?= <Hello@Cafe.Example>\r\n'
    b'Subject: =?UTF-8?Q?Caf=C3=A9_menu?=\r\n'
    b'Date: Mon, 06 Jan 2025 10:00:00 -0500\r\n'
    b'List-Unsubscribe: <mailto:u@cafe.example?subject=unsub>,\r\n'
    b' <https://cafe.example/u?x=1>\r\n'
    b'List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n\r\n'
)


def msg(frm, subj, date, lu="", lup=""):
    return {"from": frm, "subject": subj, "date": date,
            "list_unsubscribe": lu, "list_unsubscribe_post": lup}


class HeaderParsing(unittest.TestCase):
    def test_parse_header_block_decodes_and_unfolds(self):
        m = h.parse_header_block(RAW)
        self.assertEqual(h.parse_from(m["from"]), ("Café", "hello@cafe.example"))
        self.assertEqual(h.decode_str(m["subject"]), "Café menu")
        self.assertEqual(h.parse_date(m["date"]).isoformat(), "2025-01-06T15:00:00+00:00")
        links = h.parse_list_unsubscribe(m["list_unsubscribe"])
        self.assertEqual(links.https, ["https://cafe.example/u?x=1"])
        self.assertEqual(links.mailto, ["mailto:u@cafe.example?subject=unsub"])

    def test_bad_date_is_none(self):
        self.assertIsNone(h.parse_date("not a date"))
        self.assertIsNone(h.parse_date(""))

    def test_dangerous_schemes_dropped(self):
        links = h.parse_list_unsubscribe("<javascript:alert(1)>, <data:text/html,x>, <ftp://x>")
        self.assertEqual((links.https, links.http, links.mailto), ([], [], []))

    def test_classify(self):
        oc = "List-Unsubscribe=One-Click"
        self.assertEqual(h.classify("<https://a.example/u>", oc), h.ONE_CLICK)
        self.assertEqual(h.classify("<https://a.example/u>, <mailto:x@a.example>", oc), h.ONE_CLICK)
        self.assertEqual(h.classify("<https://a.example/u>, <mailto:x@a.example>", ""), h.MAILTO)
        self.assertEqual(h.classify("<mailto:x@a.example>", oc), h.MAILTO)  # no https URL
        self.assertEqual(h.classify("<https://a.example/u>", ""), h.LINK_ONLY)
        self.assertEqual(h.classify("<http://a.example/u>", oc), h.LINK_ONLY)  # http is never one-click
        self.assertEqual(h.classify("", ""), h.NONE)

    def test_parse_mailto(self):
        self.assertEqual(h.parse_mailto("mailto:a@b.example?subject=Remove%20me&body=please+stop"),
                         ("a@b.example", "Remove me", "please+stop"))
        self.assertEqual(h.parse_mailto("mailto:a@b.example?subject=x%0d%0aBcc:%20evil@x.example")[1],
                         "x Bcc: evil@x.example")  # no CR/LF survives
        with self.assertRaises(ValueError):
            h.parse_mailto("mailto:not-an-address")

    def test_aggregate(self):
        oc = "List-Unsubscribe=One-Click"
        out = h.aggregate([
            msg("A <a@x.example>", "old", "Mon, 01 Jan 2024 10:00:00 +0000", "<https://x.example/old>", oc),
            msg("A <A@X.example>", "new", "Mon, 01 Jul 2024 10:00:00 +0000", "<mailto:u@x.example>", ""),
            msg("A <a@x.example>", "mid", "Mon, 01 Apr 2024 10:00:00 +0000"),
            msg("B <b@y.example>", "only", "Mon, 01 Apr 2024 10:00:00 +0000"),
            msg("", "no sender", ""),
        ])
        self.assertEqual([s.address for s in out], ["a@x.example", "b@y.example"])
        a = out[0]
        self.assertEqual((a.count, a.latest_subject), (3, "new"))
        # headers come from the newest message that has them, as a matching pair
        self.assertEqual((a.list_unsubscribe, a.list_unsubscribe_post), ("<mailto:u@x.example>", ""))
        self.assertEqual(a.method, h.MAILTO)
        self.assertEqual(out[1].method, h.NONE)


if __name__ == "__main__":
    unittest.main()
