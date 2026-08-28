"""Build a PDF from page screenshot images. Does not OCR."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


def collect_images(directory: Path) -> list[Path]:
    images = [
        child
        for child in directory.iterdir()
        if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
    ]
    images.sort(key=lambda path: path.name.lower())
    if not images:
        raise FileNotFoundError(f"No images found in {directory}")
    return images


def build_pdf(images: list[Path], output: Path) -> None:
    import fitz

    if not images:
        raise FileNotFoundError("No images to convert")
    output.parent.mkdir(parents=True, exist_ok=True)
    merged = fitz.open()
    try:
        for image in images:
            src = fitz.open(image)
            try:
                pdf_bytes = src.convert_to_pdf()
            finally:
                src.close()
            page_pdf = fitz.open("pdf", pdf_bytes)
            try:
                merged.insert_pdf(page_pdf)
            finally:
                page_pdf.close()
        merged.save(output)
    finally:
        merged.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="images_to_pdf.py",
        description="Concatenate screenshot images into a PDF (no OCR).",
    )
    parser.add_argument("directory", type=Path, help="directory of page images")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output PDF path (default: <directory>.pdf)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    directory = args.directory.expanduser().resolve()
    if not directory.is_dir():
        raise SystemExit(f"Not a directory: {directory}")
    images = collect_images(directory)
    output = args.output or directory.with_suffix(".pdf")
    build_pdf(images, output)
    print(f"wrote {output} ({len(images)} pages)")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
