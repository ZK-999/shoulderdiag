# AOL Unsubscriber

Scans your AOL inbox (read-only, headers only), groups recurring senders, and lets you
tick the ones to unsubscribe from in a local web page.

## Setup (Windows, PowerShell)

1. Create an AOL **app password**: AOL Account Security -> Generate app password.
2. Install:
   ```powershell
   cd aol-unsubscriber
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Provide credentials (or skip this and you'll be prompted; nothing is saved to disk):
   ```powershell
   $env:AOL_USER = "you@aol.com"
   $env:AOL_APP_PASSWORD = "your-app-password"
   ```

## Run

```powershell
python app.py                 # scan last 12 months, open http://127.0.0.1:5000/
python app.py --months 6 --min-count 3 --port 5050
python app.py --demo          # fake data, no login, always dry run
```

Options: `--months` (default 12), `--min-count` (hide senders with fewer emails, default 2),
`--batch-size`, `--port`, `--allowlist`, `--no-browser`.

In the page: tick senders, leave **Dry run** on to preview, untick it for a real run
(you'll get a confirmation prompt), then click **Unsubscribe selected**.

## What each method does

| Label | Action |
|---|---|
| One-click | `List-Unsubscribe-Post` contains `List-Unsubscribe=One-Click` and there is an https URL: HTTP POST with body `List-Unsubscribe=One-Click`. Redirects are not followed. |
| Mailto | Email sent via `smtp.aol.com:465` to the mailto address, using the header's subject/body. |
| Link only | **Never requested automatically.** Shown as a clickable link in the results for you to open. |
| None | Listed under "block manually in AOL". |

Precedence when several are offered: One-click, then Mailto, then Link only.

Results show `success`, `failed` (with reason), `manual`, `skipped` (allowlist) or `dry-run`,
and are appended to `unsubscribe_log.csv`.

## Allowlist

Put addresses in `allowlist.txt`, one per line (`@example.com` protects a whole domain,
`#` starts a comment). Those senders are never unsubscribed, in any mode.

## Safety notes

- IMAP uses `EXAMINE` (read-only) and `BODY.PEEK`; it never marks, moves or deletes mail.
- The server binds to 127.0.0.1, rejects non-localhost `Host` headers, and requires a
  per-run token on the POST. The browser sends only sender addresses; URLs come from the
  server's own scan data.
- One-click POSTs refuse non-https URLs and hosts that resolve to private/loopback addresses.
- Only `http(s)` and `mailto` entries from headers are ever used.
- A mailto unsubscribe tells the sender your address is live, same as any unsubscribe.
  Spammers can abuse this; use it only for senders you actually signed up with.

## Tests

```powershell
python -m unittest discover -s tests -v
```
