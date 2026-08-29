#!/usr/bin/env python3
"""Accept a zip of Kindle page PNGs (or loose images) from Windows over Tailscale."""
from __future__ import annotations

import cgi
import html
import json
import os
import secrets
import shutil
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(os.environ.get("KINDLE_PAGES_ROOT", "/opt/AI-reads-books-page-by-page/kindle_pages"))
PDF_DIR = Path(os.environ.get("KINDLE_PDF_DIR", "/opt/AI-reads-books-page-by-page/kindle_pdfs"))
TOKEN = os.environ.get("KINDLE_PAGES_TOKEN") or secrets.token_urlsafe(16)
HOST = os.environ.get("KINDLE_PAGES_HOST", "0.0.0.0")
PORT = int(os.environ.get("KINDLE_PAGES_PORT", "18766"))
MAX_BYTES = int(os.environ.get("KINDLE_PAGES_MAX_BYTES", str(1500 * 1024 * 1024)))
STATUS_FILE = ROOT / "_upload_status.json"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
READY_NAME = "_ready.json"
PDF_READY_DIR = PDF_DIR / "_ready"


def _image_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def _books() -> list[dict]:
    if not ROOT.is_dir():
        return []
    books = []
    for child in sorted(ROOT.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        books.append(
            {
                "name": child.name,
                "images": _image_count(child),
                "ready": (child / READY_NAME).is_file(),
                "processed": (child / "_processed.json").is_file(),
            }
        )
    return books


def _images() -> list[str]:
    names: list[str] = []
    for book in _books():
        names.append(f"{book['name']} ({book['images']})")
    return names


def _pdfs() -> list[str]:
    if not PDF_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in PDF_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )


def _status() -> dict:
    books = _books()
    pdfs = _pdfs()
    return {
        "books": books,
        "pdfs": pdfs,
        "received_images": sum(b["images"] for b in books),
        "ready": any(b["ready"] and not b["processed"] for b in books),
        "dest": str(ROOT),
        "pdf_dir": str(PDF_DIR),
    }


def _write_status() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(_status(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _page() -> bytes:
    status = _status()
    rows = "".join(
        f"<li>{html.escape(b['name'])}: {b['images']} 枚"
        f"{'（処理済み）' if b['processed'] else '（受付）' if b['ready'] else ''}</li>"
        for b in status["books"]
    ) or "<li>まだ無い</li>"
    pdf_rows = "".join(f"<li>{html.escape(name)}</li>" for name in status["pdfs"]) or "<li>まだ無い</li>"
    body = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>本のアップロード</title>
<style>
body {{ font-family: sans-serif; max-width: 42rem; margin: 2rem auto; line-height: 1.5; }}
code {{ background: #f3f3f3; padding: 0.1em 0.3em; }}
form {{ border: 1px solid #ccc; padding: 1rem; margin: 1rem 0; }}
</style>
</head>
<body>
<h1>本を送る</h1>
<p>同じ受け取り口で <strong>PDF</strong> と <strong>ページ画像の ZIP</strong> のどちらでもよい。ZIP は本ごとに別のファイル名にする。</p>
<p>画像 {status["received_images"]} 枚 / PDF {len(status["pdfs"])} 冊。</p>
<form method="post" enctype="multipart/form-data" action="/upload?token={html.escape(TOKEN)}">
<input type="file" name="file" accept=".pdf,.zip,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp,application/pdf,application/zip" multiple required>
<button type="submit">アップロード</button>
</form>
<h2>ZIP / 画像</h2>
<ul>{rows}</ul>
<h2>PDF</h2>
<ul>{pdf_rows}</ul>
</body>
</html>
"""
    return body.encode("utf-8")


def _safe_name(raw: str) -> str:
    name = Path(raw.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        return ""
    return name


def _safe_book_dir(zip_filename: str) -> Path:
    stem = Path(zip_filename).stem.strip() or "book"
    stem = stem.replace("/", "_").replace("\\", "_")
    if stem in {".", ".."}:
        stem = "book"
    dest = ROOT / stem
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _extract_zip(archive: Path, book_dir: Path) -> int:
    saved = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _safe_name(info.filename)
            if not name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            dest = book_dir / name
            with zf.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            saved += 1
    if saved > 0:
        ready = {
            "zip": archive.name,
            "images": saved,
            "dir": str(book_dir),
        }
        (book_dir / READY_NAME).write_text(
            json.dumps(ready, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return saved


def _mark_pdf_ready(dest: Path) -> None:
    PDF_READY_DIR.mkdir(parents=True, exist_ok=True)
    marker = PDF_READY_DIR / (dest.stem + ".json")
    marker.write_text(
        json.dumps({"pdf": str(dest), "name": dest.name}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _save_pdf_bytes(dest: Path, source) -> int:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest.open("wb") as out:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                dest.unlink(missing_ok=True)
                raise ValueError(f"too large: {dest.name}")
            out.write(chunk)
    if written < 5:
        dest.unlink(missing_ok=True)
        raise ValueError(f"empty PDF: {dest.name}")
    _mark_pdf_ready(dest)
    return written


def _extract_pdfs_from_zip(archive: Path) -> int:
    saved = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = _safe_name(info.filename)
            if not name or Path(name).suffix.lower() != ".pdf":
                continue
            dest = PDF_DIR / name
            with zf.open(info) as src:
                _save_pdf_bytes(dest, src)
            saved += 1
            print(f"saved PDF {name} from zip {archive.name}", flush=True)
    return saved


def _save_item(item) -> str:
    filename = _safe_name(getattr(item, "filename", "") or "")
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in IMAGE_SUFFIXES | {".zip", ".pdf"}:
        raise ValueError(f"not a PDF, image, or zip: {filename or '(empty)'}")
    dest = ROOT / filename
    if suffix == ".pdf":
        dest = PDF_DIR / filename
        written = _save_pdf_bytes(dest, item.file)
        print(f"saved PDF {filename} ({written} bytes)", flush=True)
        return filename
    written = 0
    with dest.open("wb") as out:
        while True:
            chunk = item.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                dest.unlink(missing_ok=True)
                raise ValueError(f"too large: {filename}")
            out.write(chunk)
    if suffix == ".zip":
        pdfs = _extract_pdfs_from_zip(dest)
        book_dir = _safe_book_dir(filename)
        n = _extract_zip(dest, book_dir)
        print(
            f"extracted {n} images and {pdfs} PDFs from {filename} ({written} bytes)",
            flush=True,
        )
        dest.unlink(missing_ok=True)
        if n == 0 and pdfs == 0:
            raise ValueError(f"no images or PDFs in zip: {filename}")
        if n == 0:
            shutil.rmtree(book_dir, ignore_errors=True)
        return f"zip:{n}+pdf:{pdfs}"
    loose = ROOT / "_loose"
    loose.mkdir(parents=True, exist_ok=True)
    shuffled = loose / filename
    dest.replace(shuffled)
    print(f"saved {filename} ({written} bytes)", flush=True)
    return filename


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
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ=environ,
            keep_blank_values=True,
        )
        items = form["file"] if "file" in form else []
        if not isinstance(items, list):
            items = [items]
        ROOT.mkdir(parents=True, exist_ok=True)
        try:
            for item in items:
                _save_item(item)
        except ValueError as exc:
            self._deny(400, str(exc))
            return
        _write_status()
        self.send_response(303)
        self.send_header("Location", f"/?token={TOKEN}")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    PDF_READY_DIR.mkdir(parents=True, exist_ok=True)
    _write_status()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"KINDLE_PAGES_TOKEN={TOKEN}", flush=True)
    print(f"listening on http://{HOST}:{PORT}/?token={TOKEN}", flush=True)
    print(f"dest={ROOT}", flush=True)
    print(f"pdf_dir={PDF_DIR}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
