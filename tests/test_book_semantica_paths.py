import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from book_semantica import paths


class SemanticaPythonTests(unittest.TestCase):
    def test_default_interpreter_is_hermes_venv(self):
        self.assertEqual(
            paths.DEFAULT_SEMANTICA_PYTHON,
            Path("/var/lib/happy/.local/share/semantica/venv/bin/python"),
        )

    def test_resolve_semantica_python_reads_env(self):
        with TemporaryDirectory() as tmp:
            fake = Path(tmp) / "python"
            fake.write_text("#!/bin/sh\n")
            fake.chmod(0o755)
            old = os.environ.get("SEMANTICA_PYTHON")
            os.environ["SEMANTICA_PYTHON"] = str(fake)
            try:
                self.assertEqual(paths.resolve_semantica_python(), fake.resolve())
            finally:
                if old is None:
                    os.environ.pop("SEMANTICA_PYTHON", None)
                else:
                    os.environ["SEMANTICA_PYTHON"] = old


class OutputPathTests(unittest.TestCase):
    def test_forbidden_path_is_hermes_knowledge_work(self):
        self.assertEqual(
            paths.HERMES_GRAPH_PATH,
            Path("/var/lib/happy/.local/state/hermes/semantica-knowledge-work.json"),
        )

    def test_book_output_dir_is_under_book_analysis_semantica(self):
        out = paths.book_output_dir("労務入門.ocr")
        self.assertEqual(out.parts[-3:], ("book_analysis", "semantica", "労務入門.ocr"))
        self.assertTrue(str(out).startswith(str(paths.REPO_ROOT)))

    def test_assert_safe_output_path_rejects_hermes_graph(self):
        with self.assertRaises(paths.ForbiddenOutputPath):
            paths.assert_safe_output_path(paths.HERMES_GRAPH_PATH)

    def test_assert_safe_output_path_rejects_symlink_to_hermes_graph(self):
        with TemporaryDirectory() as tmp:
            link = Path(tmp) / "alias.json"
            try:
                link.symlink_to(paths.HERMES_GRAPH_PATH)
            except OSError:
                self.skipTest("cannot create symlink to Hermes graph")
            with self.assertRaises(paths.ForbiddenOutputPath):
                paths.assert_safe_output_path(link)

    def test_assert_safe_output_path_allows_book_dir(self):
        target = paths.book_output_dir("労務入門.ocr") / "graph.json"
        paths.assert_safe_output_path(target)

    def test_assert_output_directory_accepts_ocr_suffix_path(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "採用入門.ocr"
            self.assertEqual(paths.assert_output_directory(out), out)

    def test_assert_output_directory_rejects_existing_file(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "notes.txt"
            target.write_text("x\n", encoding="utf-8")
            with self.assertRaises(paths.ForbiddenOutputPath) as caught:
                paths.assert_output_directory(target)
            self.assertIn("must be a directory, not a file", str(caught.exception))

    def test_assert_output_directory_rejects_hermes_graph(self):
        with self.assertRaises(paths.ForbiddenOutputPath):
            paths.assert_output_directory(paths.HERMES_GRAPH_PATH)

    def test_book_output_dir_is_not_hermes_graph(self):
        out = paths.book_output_dir("労務入門.ocr")
        self.assertNotEqual(out.resolve(), paths.HERMES_GRAPH_PATH.resolve())
        self.assertFalse(
            out.resolve() == paths.HERMES_GRAPH_PATH.parent.resolve()
            and out.name == paths.HERMES_GRAPH_PATH.name
        )


class LaunchScriptTests(unittest.TestCase):
    def test_script_does_not_prepend_repo_venv_site_packages(self):
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_book_semantica.sh"
        text = script.read_text(encoding="utf-8")
        self.assertNotIn(".venv/lib/python3.10/site-packages", text)
        self.assertIn('PYTHONPATH="${PWD}${PYTHONPATH:+:${PYTHONPATH}}"', text)
        self.assertIn("SEMANTICA_PYTHON", text)
        self.assertIn("bws", text)
        self.assertIn("book_semantica.resolve_xai_key", text)
        self.assertIn(".venv/bin/python3", text)
        self.assertIn('env -u PYTHONPATH', text)


class ServePortTests(unittest.TestCase):
    def test_default_viewer_port_is_8767(self):
        self.assertEqual(paths.DEFAULT_VIEWER_PORT, 8767)

    def test_hermes_explorer_port_is_rejected(self):
        with self.assertRaises(ValueError):
            paths.assert_viewer_port(8766)


if __name__ == "__main__":
    unittest.main()
