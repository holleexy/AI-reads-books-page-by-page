import sys
import os
import importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from read_books import BookConfig


def test_analysis_interval_none_disables_interval():
    """analysis_interval=None should disable interval analysis (falsy check)."""
    config = BookConfig(
        pdf_path=Path("dummy.pdf"),
        analysis_interval=None,
    )
    assert config.analysis_interval is None
    assert not config.analysis_interval  # falsy — guards at line 336


def test_max_book_workers_env_default():
    """MAX_BOOK_WORKERS defaults to 2 when env var is not set."""
    os.environ.pop("MAX_BOOK_WORKERS", None)
    import run_all_books
    importlib.reload(run_all_books)
    assert run_all_books.MAX_BOOK_WORKERS == 2


def test_max_book_workers_env_override():
    """MAX_BOOK_WORKERS can be overridden via environment variable."""
    os.environ["MAX_BOOK_WORKERS"] = "4"
    import run_all_books
    importlib.reload(run_all_books)
    assert run_all_books.MAX_BOOK_WORKERS == 4
    os.environ.pop("MAX_BOOK_WORKERS", None)
