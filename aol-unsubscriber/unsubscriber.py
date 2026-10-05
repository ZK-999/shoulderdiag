"""Unsubscribe actions, allowlist handling and CSV logging."""

import csv
import ipaddress
import os
import smtplib
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlsplit

import requests

import headers as h

SMTP_HOST = "smtp.aol.com"
SMTP_PORT = 465

SUCCESS, FAILED, MANUAL, DRY_RUN, SKIPPED = "success", "failed", "manual", "dry-run", "skipped"


@dataclass
class Result:
    address: str
    method: str
    status: str
    detail: str = ""
    link: str = ""  # clickable URL, set only for manual results


def load_allowlist(path):
    """Read allowlist.txt: one address per line, '#' comments, '@domain.com' for a whole domain."""
    entries = set()
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip().lower()
                if line:
                    entries.add(line)
    except FileNotFoundError:
        pass
    return entries


def is_allowlisted(address, allowlist):
    address = address.lower()
    return address in allowlist or "@" + address.rpartition("@")[2] in allowlist


def _check_public_https(url):
    """Refuse non-https URLs and hosts that resolve to private/loopback addresses."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("not an https URL")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"cannot resolve host ({exc.strerror or exc})")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError("host resolves to a non-public address")


def one_click_post(url, session=None, timeout=20):
    """RFC 8058 one-click POST. Redirects are not followed (a redirect would become a GET)."""
    _check_public_https(url)
    post = (session or requests).post
    resp = post(
        url,
        data="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "aol-unsubscriber/1.0"},
        timeout=timeout,
        allow_redirects=False,
    )
    return resp.status_code, resp.headers.get("Location", "")


class _Smtp:
    """Lazily opened, reused SMTP-over-SSL connection."""

    def __init__(self, user, password, host=SMTP_HOST, port=SMTP_PORT):
        self._user, self._password, self._host, self._port = user, password, host, port
        self._conn = None

    def send(self, to, subject, body):
        msg = EmailMessage()
        msg["From"] = self._user
        msg["To"] = to
        msg["Subject"] = subject or "unsubscribe"
        msg.set_content(body or "unsubscribe")
        for attempt in (1, 2):
            try:
                if self._conn is None:
                    conn = smtplib.SMTP_SSL(self._host, self._port,
                                            context=ssl.create_default_context(), timeout=30)
                    conn.login(self._user, self._password)
                    self._conn = conn
                self._conn.send_message(msg)
                return
            except smtplib.SMTPServerDisconnected:
                self.close()
                if attempt == 2:
                    raise

    def close(self):
        if self._conn is not None:
            try:
                self._conn.quit()
            except Exception:
                pass
            self._conn = None


def _first_valid_mailto(urls):
    last_err = ValueError("no mailto link")
    for url in urls:
        try:
            return h.parse_mailto(url)
        except ValueError as exc:
            last_err = exc
    raise last_err


def process(senders, *, dry_run, allowlist, user="", password="", session=None, smtp=None):
    """Unsubscribe from each Sender and return a list of Result.

    dry_run=True performs no network access at all. Allowlisted senders are
    skipped in every mode. Link-only senders are never requested.
    """
    results = []
    smtp = smtp or _Smtp(user, password)
    try:
        for s in senders:
            method, links = s.method, s.links
            if is_allowlisted(s.address, allowlist):
                results.append(Result(s.address, method, SKIPPED, "on allowlist"))
            elif method == h.ONE_CLICK:
                url = links.https[0]
                host = urlsplit(url).hostname
                if dry_run:
                    results.append(Result(s.address, method, DRY_RUN, f"would POST one-click to {host}"))
                    continue
                try:
                    code, location = one_click_post(url, session)
                except (requests.RequestException, ValueError) as exc:
                    results.append(Result(s.address, method, FAILED, f"{type(exc).__name__}: {exc}"))
                    continue
                if 200 <= code < 300:
                    results.append(Result(s.address, method, SUCCESS, f"HTTP {code}"))
                elif 300 <= code < 400:
                    results.append(Result(s.address, method, MANUAL,
                                          f"HTTP {code} redirect (not followed); open the link yourself",
                                          link=url))
                else:
                    results.append(Result(s.address, method, FAILED, f"HTTP {code}"))
            elif method == h.MAILTO:
                try:
                    to, subject, body = _first_valid_mailto(links.mailto)
                except ValueError as exc:
                    results.append(Result(s.address, method, FAILED, str(exc)))
                    continue
                if dry_run:
                    results.append(Result(s.address, method, DRY_RUN, f"would email {to} (subject: {subject or 'unsubscribe'})"))
                    continue
                try:
                    smtp.send(to, subject, body)
                    results.append(Result(s.address, method, SUCCESS, f"email sent to {to}"))
                except (smtplib.SMTPException, OSError) as exc:
                    results.append(Result(s.address, method, FAILED, f"{type(exc).__name__}: {exc}"))
            elif method == h.LINK_ONLY:
                url = (links.https or links.http)[0]
                results.append(Result(s.address, method, MANUAL, "open and confirm yourself", link=url))
            else:
                results.append(Result(s.address, method, MANUAL, "no unsubscribe header; block manually in AOL"))
    finally:
        smtp.close()
    return results


def _safe_cell(value):
    """Neutralise spreadsheet formula injection (log is likely opened in Excel)."""
    value = str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def append_log(path, results, dry_run):
    """Append results to the CSV log (header row written when the file is new)."""
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    now = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "mode", "sender", "method", "status", "detail", "link"])
        for r in results:
            w.writerow([now, "dry-run" if dry_run else "live", _safe_cell(r.address),
                        r.method, r.status, _safe_cell(r.detail), r.link])
