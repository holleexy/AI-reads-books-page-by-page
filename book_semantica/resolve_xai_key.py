"""Resolve an xAI token the same way read_books.py does.

Stdout is the token only. Logs go to stderr. Do not print the token elsewhere.
"""

from __future__ import annotations

import os
import sys


def resolve_token() -> str | None:
    env_key = os.environ.get("XAI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    try:
        import xai_oauth
    except ImportError:
        return None
    try:
        token = xai_oauth.resolve_access_token()
    except Exception as exc:
        print(f"xAI OAuth failed: {exc}", file=sys.stderr)
        return None
    if token and str(token).strip():
        return str(token).strip()
    return None


def main() -> int:
    token = resolve_token()
    if not token:
        return 1
    sys.stdout.write(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
