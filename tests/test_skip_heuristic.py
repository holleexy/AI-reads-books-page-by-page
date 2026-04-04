import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from read_books import should_skip_locally


def test_blank_page():
    assert should_skip_locally("") is True
    assert should_skip_locally("   \n\n  ") is True


def test_very_short_page():
    assert should_skip_locally("42") is True
    assert should_skip_locally("Page 15") is True


def test_copyright_page():
    text = "Copyright 2024 Publisher Inc. All rights reserved. ISBN 978-4-123456-78-9"
    assert should_skip_locally(text) is True


def test_colophon_page():
    text = "奥付\n著者 山田太郎\n発行 2024年4月1日\n発行所 出版社名"
    assert should_skip_locally(text) is True


def test_real_content_not_skipped():
    text = "リーダーシップとは、他者に影響を与え、共通の目標に向かって行動を促す能力である。これは生まれつきの資質ではなく、学習と実践を通じて開発できるスキルである。"
    assert should_skip_locally(text) is False


def test_short_but_meaningful_not_skipped():
    text = "第1章 戦略的思考の基本原則と実践的なフレームワーク"
    assert should_skip_locally(text) is False


def test_page_with_contents_keyword_in_real_text():
    """Codex review: 'contents' should NOT trigger skip in real content."""
    text = "The contents of this chapter explore the fundamental principles of leadership and management in modern organizations."
    assert should_skip_locally(text) is False


def test_page_with_references_in_real_text():
    """Codex review: 'references' should NOT trigger skip in real content."""
    text = "This framework references several key studies from the field of organizational behavior."
    assert should_skip_locally(text) is False


def test_isbn_in_short_page():
    text = "ISBN 978-4-123456-78-9\nPrinted in Japan"
    assert should_skip_locally(text) is True
