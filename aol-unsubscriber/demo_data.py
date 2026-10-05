"""Fake raw header blocks for --demo mode and tests. Goes through the real parser."""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from headers import parse_header_block


def _block(frm, subject, when, lu=None, lup=None):
    lines = [f"From: {frm}", f"Subject: {subject}", f"Date: {format_datetime(when)}"]
    if lu:
        lines.append(f"List-Unsubscribe: {lu}")
    if lup:
        lines.append(f"List-Unsubscribe-Post: {lup}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


def demo_messages():
    now = datetime.now(timezone.utc)
    spec = [
        # (from, subject, count, List-Unsubscribe, List-Unsubscribe-Post)
        ('"Daily Deals" <deals@shop-one.example>', "50% off today only", 40,
         "<https://shop-one.example/unsub?id=abc>, <mailto:unsub@shop-one.example>",
         "List-Unsubscribe=One-Click"),
        ("News Letter <news@weekly-digest.example>", "Your weekly digest", 25,
         "<mailto:leave@weekly-digest.example?subject=unsubscribe%20me>", None),
        ("Travel Co <offers@travel.example>", "Summer flights from $99", 12,
         "<https://travel.example/preferences?u=42>", None),
        ("Trusted Shop <news@trusted-shop.example>", "New arrivals", 9,
         "<https://trusted-shop.example/u>", "List-Unsubscribe=One-Click"),
        ("Bank Alerts <alerts@bank.example>", "Statement ready", 8, None, None),
        ("=?UTF-8?B?Q2Fmw6k=?= <hello@cafe.example>", "=?UTF-8?Q?Caf=C3=A9_menu_update?=", 5,
         "<javascript:alert(1)>", None),
        ("Old Friend <friend@example.org>", "lunch?", 3, None, None),
        ("Odd Sender <odd@weird.example>", "Hi", 4, "<http://weird.example/unsub>", None),
    ]
    out = []
    for frm, subj, n, lu, lup in spec:
        for i in range(n):
            out.append(parse_header_block(_block(frm, subj if i == 0 else f"{subj} #{i}",
                                                 now - timedelta(days=(i + 1) * 6 if i else 1), lu, lup)))
    return out
