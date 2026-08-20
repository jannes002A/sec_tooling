#!/usr/bin/env python3
"""
Extract all text from a given image via OCR, print it to stdout,
and save it to a .txt file next to the image.

Includes image preprocessing (grayscale, upscaling, contrast,
denoising, binarization) to improve OCR quality.

Usage:
    python image_ocr.py <path/to/image.png>
    python image_ocr.py --lang deu screenshot.png
    python image_ocr.py --lang deu+eng --psm 11 screenshot.png
    python image_ocr.py --no-preprocess photo.jpg

Requirements:
    pip install pillow pytesseract
    Tesseract OCR must be installed on the system:
        - Linux:   sudo apt install tesseract-ocr
        - macOS:   brew install tesseract
        - Windows: https://github.com/UB-Mannheim/tesseract/wiki
    For non-English languages install the language pack, e.g.:
        sudo apt install tesseract-ocr-deu
"""

import argparse
import sys
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps


def preprocess(img: Image.Image, threshold: int, invert: bool) -> Image.Image:
    """Prepare the image for better OCR results."""
    # Grayscale
    img = ImageOps.grayscale(img)

    # Invert for light text on dark backgrounds
    if invert:
        img = ImageOps.invert(img)

    # Upscale small images (Tesseract works best around ~300 DPI)
    if img.width < 1500:
        factor = 3
        img = img.resize((img.width * factor, img.height * factor), Image.LANCZOS)

    # Boost contrast and reduce noise
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # Binarize: everything above threshold -> white, below -> black
    img = img.point(lambda p: 255 if p > threshold else 0)

    return img


def extract_text(
    image_path: Path,
    lang: str,
    psm: int,
    threshold: int,
    invert: bool,
    do_preprocess: bool,
) -> str:
    """Run OCR on the image and return the extracted text."""
    with Image.open(image_path) as img:
        if do_preprocess:
            img = preprocess(img, threshold=threshold, invert=invert)
        config = f"--oem 3 --psm {psm}"
        return pytesseract.image_to_string(img, lang=lang, config=config)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract text from an image, print it, and save it as a .txt file."
    )
    parser.add_argument("image", type=Path, help="Path to the image file")
    parser.add_argument(
        "--lang",
        default="eng",
        help="OCR language(s), e.g. 'eng', 'deu', or 'deu+eng' (default: eng). "
        "Requires the matching Tesseract language pack.",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=6,
        help="Tesseract page segmentation mode (default: 6 = uniform text block; "
        "try 11 for sparse text like UI screenshots, 4 for columns).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=160,
        help="Binarization threshold 0-255 (default: 160). Tune if text is lost.",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Invert the image first (use for light text on dark backgrounds).",
    )
    parser.add_argument(
        "--no-preprocess",
        action="store_true",
        help="Skip preprocessing and run OCR on the raw image.",
    )
    args = parser.parse_args()

    image_path: Path = args.image

    if not image_path.is_file():
        print(f"Error: file not found: {image_path}", file=sys.stderr)
        return 1

    try:
        text = extract_text(
            image_path,
            lang=args.lang,
            psm=args.psm,
            threshold=args.threshold,
            invert=args.invert,
            do_preprocess=not args.no_preprocess,
        )
    except pytesseract.TesseractNotFoundError:
        print(
            "Error: Tesseract OCR is not installed or not on PATH.\n"
            "Install it, e.g. 'sudo apt install tesseract-ocr' (Linux) "
            "or 'brew install tesseract' (macOS).",
            file=sys.stderr,
        )
        return 1
    except pytesseract.TesseractError as e:
        print(
            f"Tesseract error: {e}\n"
            f"Hint: if the language '{args.lang}' is missing, install its pack, "
            f"e.g. 'sudo apt install tesseract-ocr-deu' for German.",
            file=sys.stderr,
        )
        return 1
    except Exception as e:
        print(f"Error during OCR: {e}", file=sys.stderr)
        return 1

    # Print extracted text to stdout
    print(text)

    # Save text to a file with the same name as the image, but .txt
    txt_path = image_path.with_suffix(".txt")
    txt_path.write_text(text, encoding="utf-8")

    print(f"[Text saved to: {txt_path}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
