"""
app.py - AWS Lambda handler for the PDF tagging pipeline.

Trigger: S3 ObjectCreated event on the input bucket.
Action: Download the PDF to /tmp, run the pipeline, and write structured
CSV and JSON results back to the results S3 bucket.

Environment variables:
    RESULTS_BUCKET - name of the S3 bucket for result files
"""

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

from classifier import DocumentClassifier
from generic_field_extractor import extract_generic_fields
from metadata_extractor import extract_metadata
from record_formatter import record_to_csv_text, record_to_json_text
from summarizer import summarize
from text_extractor import extract_text_from_pdf


log = logging.getLogger()
log.setLevel(logging.INFO)

s3 = boto3.client("s3")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")

# Reuse the fitted vectorizer across warm Lambda invocations.
classifier = DocumentClassifier()


def _process_one_object(bucket: str, key: str) -> dict:
    start = time.perf_counter()
    log.info(f"Processing s3://{bucket}/{key}")

    local_path = f"/tmp/{os.path.basename(key)}"
    s3.download_file(bucket, key, local_path)

    try:
        doc = extract_text_from_pdf(local_path)

        cls = classifier.classify(doc["text"])
        log.info(
            f"  Category: {cls['category']} "
            f"(confidence margin: {cls['confidence']:.3f})"
        )

        metadata = extract_metadata(cls["category"], doc["text"])
        generic_fields = extract_generic_fields(doc["text"])
        summary = summarize(doc["text"], num_sentences=3)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        record = {
            "document_id": str(uuid.uuid4()),
            "filename": doc["filename"],
            "source_bucket": bucket,
            "source_key": key,
            "s3_uri": f"s3://{bucket}/{key}",
            "category": cls["category"],
            "best_category_match": cls.get("best_match"),
            "confidence": float(cls["confidence"]),
            "category_scores": cls["scores"],
            "category_alias_scores": cls.get("alias_scores"),
            "category_tfidf_scores": cls.get("tfidf_scores"),
            "category_structural_scores": cls.get("structural_scores"),
            "num_pages": doc["num_pages"],
            "char_count": doc["char_count"],
            "extractor": doc["extractor"],
            "summary": summary,
            "metadata": metadata,
            "keyword_fields": generic_fields["fields"],
            "keyword_matches": generic_fields["matches"],
            "processed_at": now,
        }

        if RESULTS_BUCKET:
            csv_key = f"results/csv/{record['document_id']}.csv"
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=csv_key,
                Body=record_to_csv_text(record).encode("utf-8"),
                ContentType="text/csv",
            )
            log.info(f"  Wrote CSV sidecar: s3://{RESULTS_BUCKET}/{csv_key}")

            json_key = f"results/json/{record['document_id']}.json"
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=json_key,
                Body=record_to_json_text(record).encode("utf-8"),
                ContentType="application/json",
            )
            log.info(f"  Wrote JSON sidecar: s3://{RESULTS_BUCKET}/{json_key}")
        else:
            log.warning("RESULTS_BUCKET is not set; result sidecars were not written")

        elapsed = (time.perf_counter() - start) * 1000
        log.info(f"  Done in {elapsed:.1f} ms")
        return record

    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass


def lambda_handler(event, context):  # noqa: ARG001
    log.info(f"Received event with {len(event.get('Records', []))} record(s)")

    processed = []
    failed = []

    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key = unquote_plus(rec["s3"]["object"]["key"])

        if not key.lower().endswith(".pdf"):
            log.warning(f"Skipping non-PDF object: {key}")
            continue

        try:
            record = _process_one_object(bucket, key)
            processed.append({
                "document_id": record["document_id"],
                "filename": record["filename"],
                "category": record["category"],
            })
        except ClientError as e:
            log.exception(f"AWS error processing {key}")
            failed.append({"key": key, "error": str(e)})
        except Exception as e:
            log.exception(f"Pipeline error processing {key}")
            failed.append({"key": key, "error": str(e)})

    return {
        "statusCode": 200 if not failed else 207,
        "processed": processed,
        "failed": failed,
    }
