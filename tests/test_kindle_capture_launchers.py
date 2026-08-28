import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import kindle_capture_encoding as encoding


class KindleLauncherTests(unittest.TestCase):
    def test_cp932_reproduces_original_parser_trap(self):
        sample = encoding.sample_broken_gui_line()
        self.assertIn(b"\xe5\x8f\xb3", sample)
        self.assertTrue(encoding.cp932_quote_swallow_reproduced(sample))

    def test_current_ps1_files_do_not_hit_cp932_quote_trap(self):
        for path in encoding.PS1_FILES:
            raw = path.read_bytes()
            if raw.startswith(encoding.UTF8_BOM):
                raw = raw[len(encoding.UTF8_BOM) :]
            self.assertFalse(
                encoding.cp932_quote_swallow_reproduced(raw),
                msg=str(path),
            )

    def test_launcher_encoding_and_tokens(self):
        self.assertEqual(encoding.check_all(), [])

    def test_default_bat_calls_capture_not_gui(self):
        text = (ROOT / "scripts" / "KindleCapture.bat").read_text(encoding="ascii")
        self.assertIn("kindle_capture.ps1", text)
        self.assertNotIn("kindle_capture_gui.ps1", text)
        self.assertIn("choice /c RL", text)

    def test_ps1_does_not_use_invalid_requires_sta(self):
        for path in encoding.PS1_FILES:
            text = path.read_bytes()[len(encoding.UTF8_BOM) :].decode("ascii")
            for line in text.splitlines():
                stripped = line.strip().lower()
                if stripped.startswith("#requires") and "-sta" in stripped:
                    self.fail(f"{path} still has invalid #Requires -STA")

    def test_capture_bats_pass_sta_to_powershell(self):
        for name in (
            "KindleCapture.bat",
            "KindleCapture-Right.bat",
            "KindleCapture-Left.bat",
        ):
            text = (ROOT / "scripts" / name).read_text(encoding="ascii")
            self.assertIn("-STA", text, msg=name)

    def test_all_expected_files_exist(self):
        for path in (*encoding.PS1_FILES, *encoding.BAT_FILES):
            self.assertTrue(path.is_file(), msg=str(path))


if __name__ == "__main__":
    unittest.main()
