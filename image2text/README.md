# image_ocr.py

Extract text from an image via OCR (Tesseract), print it to stdout, and save it to a `.txt` file next to the image (same name, `.txt` extension).

The script preprocesses the image by default (grayscale, upscaling, contrast boost, denoising, binarization) to improve OCR quality.

## Requirements

- Python 3.8+
- Python packages:

  ```
  pip install pillow pytesseract
  ```

- Tesseract OCR engine (system dependency):

  | OS      | Install command / source                                  |
  |---------|-----------------------------------------------------------|
  | Linux   | `sudo apt install tesseract-ocr`                           |
  | macOS   | `brew install tesseract`                                   |
  | Windows | https://github.com/UB-Mannheim/tesseract/wiki              |

- For non-English text, install the matching language pack, e.g. German:

  ```
  sudo apt install tesseract-ocr-deu
  ```

## Usage

```
python image_ocr.py <image>
```

Examples:

```
python image_ocr.py screenshot.png                    # defaults: English, psm 6
python image_ocr.py --lang deu screenshot.png         # German
python image_ocr.py --lang deu+eng --psm 11 shot.png  # mixed languages, sparse UI text
python image_ocr.py --invert dark_theme.png           # light text on dark background
python image_ocr.py --threshold 120 image.png         # tune binarization threshold
python image_ocr.py --no-preprocess photo.jpg         # raw OCR without preprocessing
```

Output:
- Extracted text is printed to **stdout** (status messages go to stderr, so stdout can be piped cleanly).
- The text is also saved next to the input image: `screenshot.png` → `screenshot.txt`.

## Options

| Option            | Default | Description                                                                 |
|-------------------|---------|-----------------------------------------------------------------------------|
| `--lang`          | `eng`   | OCR language(s), e.g. `deu` or `deu+eng`. Requires the Tesseract language pack. |
| `--psm`           | `6`     | Page segmentation mode. `6` = uniform text block, `11` = sparse text (UI screenshots), `4` = columns. |
| `--threshold`     | `160`   | Binarization threshold (0–255). Lower it if text disappears, raise it if noise remains. |
| `--invert`        | off     | Invert the image first. Use for light text on dark backgrounds.             |
| `--no-preprocess` | off     | Skip all preprocessing and OCR the raw image.                               |

## Tips for better results

- Set the correct `--lang` — this has a large impact (umlauts, ß, accents).
- For screenshots with scattered UI text, try `--psm 11`.
- If preprocessing makes results worse (e.g. photos, anti-aliased text), use `--no-preprocess`.
- For even higher accuracy, replace Tesseract's default models with the `tessdata_best` trained data, or consider deep-learning engines like EasyOCR / PaddleOCR.

## Exit codes

- `0` – success
- `1` – file not found, Tesseract missing, missing language pack, or OCR error
