"""
text_extractor.py
-----------------
Extracts plain text from digitally-native PDFs using pdfplumber.
The pypdf fallback is intentionally commented out for the console deployment
to keep the dependency package smaller and simpler.

This module mirrors the work a single AWS Lambda function would do when
triggered by an S3 ObjectCreated event.
"""

import os
import logging
import pdfplumber
# from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> dict:
    """
    Extract text and basic metadata from a digitally-native PDF.

    Returns a dict:
        {
            "source_path": str,
            "filename": str,
            "num_pages": int,
            "text": str,            # full concatenated text
            "page_texts": list,     # per-page text
            "extractor": str,       # which library succeeded
            "char_count": int,
        }
    """
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(pdf_path)

    filename = os.path.basename(pdf_path)
    page_texts = []
    extractor = None

    # --- Primary: pdfplumber ---
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                page_texts.append(txt)
            extractor = "pdfplumber"
    except Exception as e:
        logger.error(f"pdfplumber failed on {filename}: {e}")
        page_texts = []

    # --- Optional fallback: pypdf ---
    # Keep this commented out if you want the AWS Console deployment package
    # to depend only on pdfplumber for PDF text extraction.
    #
    # if not page_texts or all(not p.strip() for p in page_texts):
    #     try:
    #         reader = PdfReader(pdf_path)
    #         page_texts = [(p.extract_text() or "") for p in reader.pages]
    #         extractor = "pypdf"
    #     except Exception as e:
    #         logger.error(f"Both extractors failed on {filename}: {e}")
    #         raise

    full_text = "\n".join(page_texts).strip()

    # Refuse empty extractions — these are likely scanned PDFs which the
    # assignment explicitly excludes (text-native focus, no per-page OCR).
    if not full_text:
        raise ValueError(
            f"{filename}: no extractable text. This PDF may be scanned/image-based; "
            "OCR is out of scope for this text-native pipeline."
        )

    return {
        "source_path": pdf_path,
        "filename": filename,
        "num_pages": len(page_texts),
        "text": full_text,
        "page_texts": page_texts,
        "extractor": extractor,
        "char_count": len(full_text),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python text_extractor.py <pdf_path>")
        sys.exit(1)
    result = extract_text_from_pdf(sys.argv[1])
    print(f"File:       {result['filename']}")
    print(f"Pages:      {result['num_pages']}")
    print(f"Extractor:  {result['extractor']}")
    print(f"Chars:      {result['char_count']}")
    print("--- First 400 chars ---")
    print(result["text"][:400])
