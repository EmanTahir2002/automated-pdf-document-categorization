"""
test_handler_locally.py — Exercise the Lambda handler without AWS access.

We stub the S3 download (just copy a local PDF instead) and the S3 CSV
write. Useful for confirming the 5-stage pipeline still works inside the
handler shape before deploying.

Run from the project root:
    python scripts/test_handler_locally.py
"""

import os
import sys
import csv
import io
import json
import shutil
from unittest.mock import MagicMock, patch
from decimal import Decimal

# Set required env vars BEFORE importing the handler
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("RESULTS_BUCKET", "test-results")

# Make lambda_src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_src"))


def _decimal_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    raise TypeError


def main():
    sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_pdfs")
    pdfs = sorted(f for f in os.listdir(sample_dir) if f.endswith(".pdf"))
    if not pdfs:
        print("No sample PDFs found. Run scripts/generate_sample_pdfs.py first.")
        sys.exit(1)

    # Patch the AWS clients that app.py creates at module load.
    # Note: we patch them AFTER import, swapping in mocks.
    import app

    # S3 download → copy from our local sample_pdfs dir to /tmp
    def fake_download_file(bucket, key, local_path):
        src = os.path.join(sample_dir, os.path.basename(key))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy(src, local_path)
    app.s3.download_file = fake_download_file

    # S3 put_object → capture CSV records into a list
    captured_csv_records = []

    def fake_put_object(**kwargs):
        body = kwargs["Body"].decode("utf-8")
        captured_csv_records.append(next(csv.DictReader(io.StringIO(body))))
        return {}

    app.s3.put_object = MagicMock(side_effect=fake_put_object)

    # Build a fake S3 event listing all sample PDFs
    event = {
        "Records": [
            {"s3": {"bucket": {"name": "fake-input-bucket"},
                    "object": {"key": pdf}}}
            for pdf in pdfs
        ]
    }

    print(f"Invoking handler with {len(pdfs)} simulated S3 events...\n")
    result = app.lambda_handler(event, None)

    print("\n--- Handler return value ---")
    print(result)

    print(f"\n--- Captured CSV records: {len(captured_csv_records)} ---")
    for item in captured_csv_records:
        metadata = json.loads(item["metadata"] or "{}")
        keyword_fields = json.loads(item["keyword_fields"] or "{}")
        # Just print the interesting parts
        view = {
            "document_id": item["document_id"],
            "filename": item["filename"],
            "category": item["category"],
            "confidence": item["confidence"],
            "metadata_keys": list(metadata.keys()),
            "keyword_field_keys": list(keyword_fields.keys()),
            "summary_chars": len(item["summary"]),
        }
        print(view)

    # Pass/fail
    if len(captured_csv_records) == len(pdfs) and not result["failed"]:
        print("\nPASS: all PDFs processed end-to-end through the handler.")
        return 0
    print("\nFAIL: some PDFs did not produce a CSV record.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
