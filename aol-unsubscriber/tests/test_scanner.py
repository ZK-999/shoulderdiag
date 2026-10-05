import imaplib
import os
import sys
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import scanner  # noqa: E402

HDR = b"From: A <a@x.example>\r\nSubject: hi\r\nDate: Mon, 01 Jul 2024 10:00:00 +0000\r\n\r\n"


class FakeImap:
    """Records commands; drops the connection once during the first FETCH."""
    instances = []
    drops = 1

    def __init__(self, *a, **k):
        self.cmds = []
        FakeImap.instances.append(self)

    def login(self, u, p):
        return "OK", []

    def select(self, mailbox, readonly=False):
        self.cmds.append(("SELECT", mailbox, readonly))
        return "OK", [b"3"]

    def uid(self, cmd, *args):
        self.cmds.append((cmd, args))
        if cmd == "SEARCH":
            return "OK", [b"1 2 3"]
        if FakeImap.drops:
            FakeImap.drops -= 1
            raise imaplib.IMAP4.abort("socket error")
        return "OK", [(b"1 (UID 1 BODY[HEADER.FIELDS (...)] {10}", HDR), b")"] * 3

    def logout(self):
        pass


class Scanner(unittest.TestCase):
    def test_readonly_peek_and_retry(self):
        FakeImap.instances, FakeImap.drops = [], 1
        with mock.patch("imaplib.IMAP4_SSL", FakeImap), mock.patch("time.sleep"):
            msgs = scanner.AolScanner("u@aol.com", "pw", log=lambda *_: None).scan(months=12, batch_size=2)
        self.assertEqual(len(msgs), 6)  # 2 batches x 3 fake items (the fake returns 3 per fetch)
        self.assertEqual(len(FakeImap.instances), 2)  # reconnected after the drop
        for inst in FakeImap.instances:
            self.assertEqual(inst.cmds[0], ("SELECT", "INBOX", True))  # read-only
        fetches = [c for i in FakeImap.instances for c in i.cmds if c[0] == "FETCH"]
        self.assertTrue(fetches and all("BODY.PEEK" in c[1][1] for c in fetches))
        allcmds = {c[0] for i in FakeImap.instances for c in i.cmds}
        self.assertTrue(allcmds <= {"SELECT", "SEARCH", "FETCH"})  # nothing that modifies

    def test_imap_date_is_locale_independent(self):
        self.assertEqual(scanner.imap_date(date(2025, 3, 5)), "05-Mar-2025")


if __name__ == "__main__":
    unittest.main()
