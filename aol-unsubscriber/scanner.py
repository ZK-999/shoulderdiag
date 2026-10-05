"""Read-only IMAP header scan of the AOL inbox.

Safety: the mailbox is opened with EXAMINE (readonly=True) and every fetch uses
BODY.PEEK, so nothing is marked read, moved, flagged or deleted. Credentials are
used only to log in and are never printed or stored.
"""

import imaplib
import ssl
import time
from datetime import date, timedelta

from headers import parse_header_block

IMAP_HOST = "imap.aol.com"
IMAP_PORT = 993
FETCH_FIELDS = "FROM SUBJECT DATE LIST-UNSUBSCRIBE LIST-UNSUBSCRIBE-POST"
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

RETRYABLE = (imaplib.IMAP4.abort, OSError, ssl.SSLError)


def imap_date(d):
    """IMAP SINCE format (locale independent): 05-Oct-2025."""
    return f"{d.day:02d}-{_MONTHS[d.month - 1]}-{d.year}"


class AolScanner:
    def __init__(self, user, password, host=IMAP_HOST, port=IMAP_PORT,
                 retries=4, timeout=60, log=print):
        self._user = user
        self._password = password
        self._host, self._port = host, port
        self._retries = retries
        self._timeout = timeout
        self._log = log
        self._imap = None

    def _connect(self):
        self._close()
        ctx = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(self._host, self._port, ssl_context=ctx, timeout=self._timeout)
        imap.login(self._user, self._password)  # imaplib.IMAP4.error here = bad login, not retried
        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            raise imaplib.IMAP4.error("could not open INBOX read-only")
        self._imap = imap

    def _close(self):
        if self._imap is not None:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None

    def _retry(self, fn):
        """Run fn(imap), reconnecting with backoff when the connection drops."""
        delay = 2
        for attempt in range(1, self._retries + 1):
            try:
                if self._imap is None:
                    self._connect()
                return fn(self._imap)
            except RETRYABLE as exc:
                self._close()
                if attempt == self._retries:
                    raise
                self._log(f"  connection problem ({type(exc).__name__}); "
                          f"reconnecting in {delay}s (attempt {attempt}/{self._retries - 1})")
                time.sleep(delay)
                delay *= 2

    def scan(self, months=12, batch_size=200, progress=None):
        """Return a list of parsed header dicts for INBOX over the last `months`."""
        since = date.today() - timedelta(days=round(months * 365.25 / 12))

        def search(imap):
            typ, data = imap.uid("SEARCH", None, "SINCE", imap_date(since))
            if typ != "OK":
                raise imaplib.IMAP4.error("SEARCH failed")
            return data[0].split() if data and data[0] else []

        uids = self._retry(search)
        total = len(uids)
        self._log(f"Found {total} messages since {since.isoformat()}")
        messages = []
        spec = f"(BODY.PEEK[HEADER.FIELDS ({FETCH_FIELDS})])"
        try:
            for i in range(0, total, batch_size):
                batch = b",".join(uids[i:i + batch_size]).decode("ascii")

                def fetch(imap, batch=batch):
                    typ, data = imap.uid("FETCH", batch, spec)
                    if typ != "OK":
                        raise imaplib.IMAP4.abort("FETCH failed")
                    return data

                for item in self._retry(fetch):
                    if isinstance(item, tuple) and len(item) > 1:
                        messages.append(parse_header_block(item[1]))
                if progress:
                    progress(min(i + batch_size, total), total)
        finally:
            self._close()
        return messages
