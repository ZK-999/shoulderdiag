"""AOL unsubscriber: scan the inbox (read-only), review in a local web UI, unsubscribe.

Usage:  python app.py [--months 12] [--min-count 2] [--port 5000] [--demo]
"""

import argparse
import getpass
import hmac
import os
import secrets
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, abort, render_template, request

import headers as h
import unsubscriber as u

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def create_app(senders, *, allowlist, user="", password="", demo=False,
               log_path=BASE_DIR / "unsubscribe_log.csv", session=None, smtp=None):
    app = Flask(__name__)
    token = secrets.token_urlsafe(24)
    by_addr = {s.address: s for s in senders}
    with_method = [s for s in senders if s.method != h.NONE]
    no_method = [s for s in senders if s.method == h.NONE]

    @app.before_request
    def guard():
        # Localhost only; rejecting other Host headers blocks DNS-rebinding attacks.
        if request.host.rsplit(":", 1)[0].strip("[]") not in ALLOWED_HOSTS:
            abort(403)

    @app.after_request
    def headers_(resp):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    @app.get("/")
    def index():
        return render_template("index.html", token=token, demo=demo, with_method=with_method,
                               no_method=no_method, is_allowlisted=lambda a: u.is_allowlisted(a, allowlist))

    @app.post("/unsubscribe")
    def unsubscribe():
        if not hmac.compare_digest(request.form.get("token", ""), token):
            abort(403)
        dry_run = demo or "dry_run" in request.form
        # Only addresses from our own scan are honoured; URLs never come from the browser.
        chosen = [by_addr[a] for a in dict.fromkeys(request.form.getlist("sender"))
                  if a in by_addr and by_addr[a].method != h.NONE]
        results = u.process(chosen, dry_run=dry_run, allowlist=allowlist,
                            user=user, password=password, session=session, smtp=smtp)
        if results:
            u.append_log(log_path, results, dry_run)
        return render_template("results.html", results=results, dry_run=dry_run,
                               log_name=Path(log_path).name)

    return app


def get_credentials():
    user = os.environ.get("AOL_USER") or input("AOL address: ").strip()
    password = os.environ.get("AOL_APP_PASSWORD") or getpass.getpass("AOL app password: ")
    if not user or not password:
        sys.exit("AOL address and app password are required.")
    return user, password


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--months", type=float, default=12, help="how far back to scan (default 12)")
    ap.add_argument("--min-count", type=int, default=2, help="hide senders with fewer emails (default 2)")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--allowlist", default=str(BASE_DIR / "allowlist.txt"))
    ap.add_argument("--demo", action="store_true", help="use fake data; no login, always dry run")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    user = password = ""
    if args.demo:
        from demo_data import demo_messages
        messages = demo_messages()
        print(f"Demo mode: {len(messages)} fake messages, no network access, dry run forced.")
    else:
        from scanner import AolScanner
        import imaplib
        user, password = get_credentials()
        print("Scanning INBOX read-only (headers only)...")
        try:
            messages = AolScanner(user, password).scan(
                months=args.months, batch_size=args.batch_size,
                progress=lambda done, total: print(f"\r  fetched {done}/{total}", end="", flush=True))
        except imaplib.IMAP4.error as exc:
            sys.exit(f"\nIMAP error: {exc}. Check AOL_USER and that AOL_APP_PASSWORD is an app password.")
        except OSError as exc:
            sys.exit(f"\nCould not reach imap.aol.com after retries: {type(exc).__name__}: {exc}")
        print()

    senders = [s for s in h.aggregate(messages) if s.count >= args.min_count]
    print(f"{len(senders)} senders with >= {args.min_count} emails.")
    allowlist = u.load_allowlist(args.allowlist)
    app = create_app(senders, allowlist=allowlist, user=user, password=password, demo=args.demo)

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Review UI: {url}  (Ctrl+C to quit)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
