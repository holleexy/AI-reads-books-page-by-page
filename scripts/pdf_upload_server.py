#!/usr/bin/env python3
"""Accept PDF uploads from the user's Windows PC over Tailscale."""

from __future__ import annotations

import cgi
import html
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEST = Path(os.environ.get("PDF_UPLOAD_DIR", "/opt/AI-reads-books-page-by-page/kindle_pdfs"))
TOKEN = os.environ.get("PDF_UPLOAD_TOKEN") or secrets.token_urlsafe(16)
HOST = os.environ.get("PDF_UPLOAD_HOST", "0.0.0.0")
PORT = int(os.environ.get("PDF_UPLOAD_PORT", "18765"))
MAX_BYTES = int(os.environ.get("PDF_UPLOAD_MAX_BYTES", str(250 * 1024 * 1024)))
STATUS_FILE = DEST / "_upload_status.json"

_DEFAULT_EXPECTED = [
    "エンジニアのための自己管理入門.pdf",
    "プロダクトマネジメントのすべて.pdf",
    "法人営業勝ちパターン大全.pdf",
]
EXPECTED = [
    name.strip()
    for name in os.environ.get("PDF_UPLOAD_EXPECTED", "").split("|")
    if name.strip()
] or _DEFAULT_EXPECTED


def _pdfs() -> list[str]:
    if not DEST.is_dir():
        return []
    return sorted(p.name for p in DEST.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def _status() -> dict:
    names = _pdfs()
    return {
        "received": names,
        "expected": EXPECTED,
        "missing": [name for name in EXPECTED if name not in names],
        "ready": all(name in names for name in EXPECTED),
    }


def _write_status() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(_status(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _page() -> bytes:
    status = _status()
    received = "".join(f"<li>{html.escape(name)}</li>" for name in status["received"]) or "<li>まだ無い</li>"
    missing = "".join(f"<li>{html.escape(name)}</li>" for name in status["missing"]) or "<li>揃った</li>"
    body = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PDF アップロード</title>
<style>
body {{ font-family: sans-serif; max-width: 42rem; margin: 2rem auto; line-height: 1.5; }}
code {{ background: #f3f3f3; padding: 0.1em 0.3em; }}
form {{ border: 1px solid #ccc; padding: 1rem; margin: 1rem 0; }}
</style>
</head>
<body>
<h1>3冊の PDF を送る</h1>
<p>Windows の Downloads から、次のファイルを選んで送信する。</p>
<ul>{missing}</ul>
<form method="post" enctype="multipart/form-data" action="/upload?token={html.escape(TOKEN)}">
<input type="file" name="file" accept=".pdf,application/pdf" multiple required>
<button type="submit">アップロード</button>
</form>
<p>受け取済み</p>
<ul>{received}</ul>
</body>
</html>
"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _token_ok(self) -> bool:
        query = parse_qs(urlparse(self.path).query)
        got = (query.get("token") or [""])[0]
        return secrets.compare_digest(got, TOKEN)

    def _deny(self, code: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/status":
            if not self._token_ok():
                self._deny(403, "forbidden")
                return
            body = json.dumps(_status(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path not in {"/", "/upload"}:
            self._deny(404, "not found")
            return
        if not self._token_ok():
            self._deny(403, "forbidden")
            return
        body = _page()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/upload" or not self._token_ok():
            self._deny(403, "forbidden")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_BYTES:
            self._deny(400, "invalid content-length")
            return
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(length),
        }
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ, keep_blank_values=True)
        items = form["file"] if "file" in form else []
        if not isinstance(items, list):
            items = [items]
        saved: list[str] = []
        DEST.mkdir(parents=True, exist_ok=True)
        for item in items:
            filename = Path(getattr(item, "filename", "") or "").name
            if not filename or Path(filename).suffix.lower() != ".pdf":
                self._deny(400, f"not a PDF: {filename or '(empty)'}")
                return
            dest = DEST / filename
            data = item.file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                self._deny(400, f"too large: {filename}")
                return
            dest.write_bytes(data)
            saved.append(filename)
            print(f"saved {filename} ({len(data)} bytes)", flush=True)
        _write_status()
        self.send_response(303)
        self.send_header("Location", f"/?token={TOKEN}")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    _write_status()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"PDF_UPLOAD_TOKEN={TOKEN}", flush=True)
    print(f"listening on http://{HOST}:{PORT}/?token={TOKEN}", flush=True)
    print(f"dest={DEST}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
