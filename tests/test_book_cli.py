import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import book_cli


class ParseArgsTests(unittest.TestCase):
    def test_requires_pdf_argument(self):
        with self.assertRaises(SystemExit):
            book_cli.parse_args([])

    def test_parses_pdf_and_options(self):
        args = book_cli.parse_args(["notes.pdf", "--pages", "60", "--interval", "0"])
        self.assertEqual(args.pdfs, ["notes.pdf"])
        self.assertEqual(args.pages, 60)
        self.assertEqual(args.interval, 0)


class ResolvePdfPathsTests(unittest.TestCase):
    def test_resolves_existing_pdf_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "book.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            paths = book_cli.resolve_pdf_paths([str(pdf)])
        self.assertEqual(paths, [pdf.resolve()])

    def test_expands_directory_to_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.pdf").write_bytes(b"%PDF")
            (root / "a.pdf").write_bytes(b"%PDF")
            (root / "skip.txt").write_text("no")
            paths = book_cli.resolve_pdf_paths([str(root)])
        names = [p.name for p in paths]
        self.assertEqual(names, ["a.pdf", "b.pdf"])

    def test_rejects_missing_file(self):
        with self.assertRaisesRegex(FileNotFoundError, "missing.pdf"):
            book_cli.resolve_pdf_paths(["missing.pdf"])

    def test_rejects_non_pdf_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt = Path(tmp) / "notes.txt"
            txt.write_text("no")
            with self.assertRaisesRegex(ValueError, "PDF"):
                book_cli.resolve_pdf_paths([str(txt)])

    def test_rejects_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, "No PDFs"):
                book_cli.resolve_pdf_paths([tmp])


class RunOptionsTests(unittest.TestCase):
    def test_default_is_full_book(self):
        args = book_cli.parse_args(["book.pdf"])
        options = book_cli.run_options_from_args(args)
        self.assertIsNone(options.test_pages)
        self.assertEqual(options.analysis_interval, 20)

    def test_interval_zero_disables_section_summaries(self):
        args = book_cli.parse_args(["book.pdf", "--interval", "0"])
        options = book_cli.run_options_from_args(args)
        self.assertIsNone(options.analysis_interval)


class MainTests(unittest.TestCase):
    def test_main_processes_given_pdf_without_waiting(self):
        import read_books
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "book.pdf"
            pdf.write_bytes(b"%PDF")
            with patch.object(read_books, "create_client") as create:
                with patch.object(read_books, "process_book") as process:
                    with patch("builtins.input", side_effect=AssertionError("should not wait")):
                        create.return_value = object()
                        read_books.main([str(pdf), "--pages", "10"])
        process.assert_called_once()
        config = process.call_args.args[1]
        self.assertEqual(config.pdf_path, pdf.resolve())
        self.assertEqual(config.test_pages, 10)


if __name__ == "__main__":
    unittest.main()
