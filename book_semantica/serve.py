"""Serve the book graph HTML. Never bind the Hermes explorer port 8766."""

from __future__ import annotations

import functools
import http.server
import os
import subprocess
from pathlib import Path

from book_semantica.paths import (
    DEFAULT_VIEWER_PORT,
    assert_safe_output_path,
    assert_viewer_port,
    resolve_semantica_python,
)


def serve_html(out_dir: Path, port: int = DEFAULT_VIEWER_PORT) -> None:
    port = assert_viewer_port(port)
    html = out_dir / "graph.html"
    if not html.is_file():
        raise FileNotFoundError(f"graph.html not found: {html}")
    assert_safe_output_path(html)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(out_dir),
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"book graph HTML at http://127.0.0.1:{port}/graph.html")
    print("this is not the Hermes explorer on 8766")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()


def serve_explorer(graph_path: Path, port: int = DEFAULT_VIEWER_PORT) -> None:
    port = assert_viewer_port(port)
    assert_safe_output_path(graph_path)
    python = resolve_semantica_python()
    env = os.environ.copy()
    subprocess.run(
        [
            str(python),
            "-m",
            "semantica.explorer",
            "--graph",
            str(graph_path),
            "--port",
            str(port),
            "--no-browser",
        ],
        check=True,
        env=env,
    )
