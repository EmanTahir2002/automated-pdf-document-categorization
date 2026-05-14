"""
process_pdf_locally.py
----------------------
Process a local PDF and write the structured result to a CSV file.

Run from the project root:
    python scripts/process_pdf_locally.py sample_pdfs/invoice_001.pdf
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_src"))

from classifier import DocumentClassifier  # noqa: E402
from generic_field_extractor import extract_generic_fields  # noqa: E402
from metadata_extractor import extract_metadata  # noqa: E402
from record_formatter import record_to_csv_text  # noqa: E402
from summarizer import summarize  # noqa: E402
from text_extractor import extract_text_from_pdf  # noqa: E402


def process_pdf(pdf_path: str) -> dict:
    doc = extract_text_from_pdf(pdf_path)
    classifier = DocumentClassifier()
    cls = classifier.classify(doc["text"])
    metadata = extract_metadata(cls["category"], doc["text"])
    generic_fields = extract_generic_fields(doc["text"])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "document_id": str(uuid.uuid4()),
        "filename": doc["filename"],
        "source_path": os.path.abspath(pdf_path),
        "category": cls["category"],
        "best_category_match": cls.get("best_match"),
        "confidence": float(cls["confidence"]),
        "category_scores": cls["scores"],
        "category_alias_scores": cls["alias_scores"],
        "category_tfidf_scores": cls["tfidf_scores"],
        "category_structural_scores": cls["structural_scores"],
        "num_pages": doc["num_pages"],
        "char_count": doc["char_count"],
        "extractor": doc["extractor"],
        "summary": summarize(doc["text"], num_sentences=3),
        "metadata": metadata,
        "keyword_fields": generic_fields["fields"],
        "keyword_matches": generic_fields["matches"],
        "processed_at": now,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to a digitally-native PDF")
    parser.add_argument(
        "--out-dir",
        default="local_results",
        help="Directory where CSV result files are written",
    )
    args = parser.parse_args()

    record = process_pdf(args.pdf_path)
    os.makedirs(args.out_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
    output_path = os.path.join(args.out_dir, f"{base_name}.csv")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(record_to_csv_text(record))

    print(f"Wrote {output_path}")
    print(f"Category: {record['category']} ({record['confidence']})")
    print(f"Keyword fields: {', '.join(record['keyword_fields'].keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
