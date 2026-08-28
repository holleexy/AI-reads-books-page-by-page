import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import images_to_pdf


MIN_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class ImagesToPdfTests(unittest.TestCase):
    def test_builds_pdf_in_filename_order(self):
        import fitz

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page_02.png").write_bytes(MIN_PNG)
            (root / "page_01.png").write_bytes(MIN_PNG)
            out = root / "book.pdf"
            images_to_pdf.build_pdf(images_to_pdf.collect_images(root), out)
            with fitz.open(out) as doc:
                self.assertEqual(doc.page_count, 2)

    def test_collects_images_sorted_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.png").write_bytes(MIN_PNG)
            (root / "a.png").write_bytes(MIN_PNG)
            (root / "notes.txt").write_text("no")
            names = [p.name for p in images_to_pdf.collect_images(root)]
        self.assertEqual(names, ["a.png", "b.png"])

    def test_rejects_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, "No images"):
                images_to_pdf.collect_images(Path(tmp))


if __name__ == "__main__":
    unittest.main()
