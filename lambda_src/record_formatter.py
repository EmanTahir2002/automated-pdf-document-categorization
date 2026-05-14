"""
record_formatter.py
-------------------
Helpers for turning one processed document record into CSV and JSON.

Nested fields are JSON-encoded inside CSV cells so the CSV stays easy to
import while preserving detailed structures such as keyword_matches.
"""

import csv
import io
import json


CSV_FIELDNAMES = [
    "document_id",
    "filename",
    "source_bucket",
    "source_key",
    "source_path",
    "s3_uri",
    "category",
    "best_category_match",
    "confidence",
    "num_pages",
    "char_count",
    "extractor",
    "summary",
    "metadata",
    "keyword_fields",
    "keyword_matches",
    "category_scores",
    "category_alias_scores",
    "category_tfidf_scores",
    "category_structural_scores",
    "processed_at",
]


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def record_to_csv_text(record: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    writer.writerow({name: _csv_value(record.get(name)) for name in CSV_FIELDNAMES})
    return output.getvalue()


def record_to_json_text(record: dict) -> str:
    return json.dumps(record, indent=2, ensure_ascii=False, default=str)
