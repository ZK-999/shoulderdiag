"""Header parsing and sender aggregation. Pure functions, no network access."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import unquote, urlsplit

ONE_CLICK = "One-click"
MAILTO = "Mailto"
LINK_ONLY = "Link only"
NONE = "None"

_MIN_DATE = datetime.min.replace(tzinfo=timezone.utc)
_BRACKETED = re.compile(r"<([^<>]*)>")
_EMAIL = re.compile(r"^[^\s@<>,;\"]+@[^\s@<>,;\"]+$")


def decode_str(value):
    """Decode RFC 2047 encoded words and unfold whitespace; never raises."""
    if not value:
        return ""
    try:
        text = str(make_header(decode_header(str(value))))
    except Exception:
        text = str(value)
    return re.sub(r"\s+", " ", text).strip()


def parse_from(raw):
    """Return (display_name, lowercase_address) from a From header."""
    name, addr = parseaddr(decode_str(raw))
    return name.strip(), addr.strip().lower()


def parse_date(raw):
    """Parse a Date header into an aware UTC datetime, or None."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(str(raw).strip())
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class UnsubLinks:
    https: list = field(default_factory=list)
    http: list = field(default_factory=list)
    mailto: list = field(default_factory=list)


def parse_list_unsubscribe(value):
    """Extract <...> entries from a List-Unsubscribe header.

    Only http(s) and mailto are kept; anything else (javascript:, data:, ...)
    is dropped so it can never reach a link or a request.
    """
    links = UnsubLinks()
    if not value:
        return links
    for item in _BRACKETED.findall(re.sub(r"\s+", "", str(value))):
        scheme = item.split(":", 1)[0].lower()
        if scheme == "https":
            links.https.append(item)
        elif scheme == "http":
            links.http.append(item)
        elif scheme == "mailto":
            links.mailto.append(item)
    return links


def is_one_click(list_unsubscribe_post):
    return bool(list_unsubscribe_post) and (
        "list-unsubscribe=one-click" in str(list_unsubscribe_post).lower().replace(" ", "")
    )


def classify(list_unsubscribe, list_unsubscribe_post):
    """Return the unsubscribe method label for a pair of header values."""
    links = parse_list_unsubscribe(list_unsubscribe)
    if links.https and is_one_click(list_unsubscribe_post):
        return ONE_CLICK
    if links.mailto:
        return MAILTO
    if links.https or links.http:
        return LINK_ONLY
    return NONE


def parse_mailto(url):
    """Parse a mailto: URL into (address, subject, body).

    Raises ValueError for anything that isn't a single plain recipient.
    CR/LF are stripped from the subject to prevent header injection.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() != "mailto":
        raise ValueError("not a mailto URL")
    addr = unquote(parts.path).strip()
    if "," in addr:  # multiple recipients: use the first only
        addr = addr.split(",", 1)[0].strip()
    if not _EMAIL.match(addr):
        raise ValueError("invalid mailto address")
    subject = body = ""
    for pair in parts.query.split("&"):
        key, _, val = pair.partition("=")
        key = key.lower()
        if key == "subject":
            subject = unquote(val)  # '+' is literal in mailto, so no unquote_plus
        elif key == "body":
            body = unquote(val)
    subject = re.sub(r"[\r\n]+", " ", subject).strip()
    return addr, subject, body


def parse_header_block(raw):
    """Parse one fetched header block (bytes) into a plain dict."""
    msg = message_from_bytes(raw)
    return {
        "from": msg.get("From", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "list_unsubscribe": msg.get("List-Unsubscribe", ""),
        "list_unsubscribe_post": msg.get("List-Unsubscribe-Post", ""),
    }


@dataclass
class Sender:
    address: str
    name: str = ""
    count: int = 0
    latest_subject: str = ""
    latest_date: datetime = None
    list_unsubscribe: str = ""
    list_unsubscribe_post: str = ""
    _unsub_date: datetime = None  # date of the message the unsub headers came from

    @property
    def method(self):
        return classify(self.list_unsubscribe, self.list_unsubscribe_post)

    @property
    def links(self):
        return parse_list_unsubscribe(self.list_unsubscribe)


def aggregate(messages):
    """Group parsed header dicts by sender address.

    The List-Unsubscribe / -Post pair is taken from the most recent message that
    carries a List-Unsubscribe header, so the two values always belong together.
    Returns a list of Sender sorted by count (descending).
    """
    senders = {}
    for m in messages:
        name, addr = parse_from(m.get("from", ""))
        if not addr:
            continue
        date = parse_date(m.get("date"))
        key_date = date or _MIN_DATE
        s = senders.get(addr)
        if s is None:
            s = senders[addr] = Sender(address=addr)
        s.count += 1
        if s.latest_date is None or key_date >= (s.latest_date or _MIN_DATE):
            s.latest_date = date
            s.latest_subject = decode_str(m.get("subject", ""))
            s.name = name or s.name
        lu = (m.get("list_unsubscribe") or "").strip()
        if lu and (s._unsub_date is None or key_date >= s._unsub_date):
            s._unsub_date = key_date
            s.list_unsubscribe = lu
            s.list_unsubscribe_post = (m.get("list_unsubscribe_post") or "").strip()
    return sorted(senders.values(), key=lambda s: (-s.count, s.address))
