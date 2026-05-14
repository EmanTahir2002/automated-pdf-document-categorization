# AWS Console Deployment Guide

**Week 3, Assignment 1 - Automated PDF Tagging Pipeline**

This guide deploys the PDF pipeline through the AWS web console. It does not use OCR, Textract, Bedrock, or any external LLM service.

The pipeline uses open-source/local Python logic for PDF text extraction, classification, metadata extraction, keyword normalization, summarization, and CSV formatting. AWS is used for S3 storage, Lambda compute, and CloudWatch logs.

---

## 1. What You Are Deploying

```text
PDF uploaded to S3 input bucket
        |
        v
S3 ObjectCreated trigger
        |
        v
Lambda app.lambda_handler
        |
        v
CSV result written to S3 results bucket
        |
        v
CloudWatch logs
```

Resources:

| Resource | Example name |
| --- | --- |
| Region | `us-east-1` |
| Input S3 bucket | `pdf-pipeline-input-<account-id>-us-east-1` |
| Results S3 bucket | `pdf-pipeline-results-<account-id>-us-east-1` |
| Lambda function | `pdf-pipeline-process-pdf` |
| Lambda handler | `app.lambda_handler` |
| Lambda runtime | Python 3.12, x86_64 |

---

## 2. Build The Lambda Package

You need a deployment zip that contains your Lambda code and Python dependencies.

From the repository root:

```bash
cd pdf_pipeline_aws/lambda_src
mkdir -p ../build/package

docker run --rm --platform linux/amd64 \
  -v "$PWD":/var/task \
  -v "$PWD/../build/package":/asset-output \
  public.ecr.aws/sam/build-python3.12:latest \
  /bin/bash -lc "pip install -r requirements.txt -t /asset-output && cp *.py /asset-output/"

cd ../build/package
zip -r ../lambda-package.zip .
```

When you open the zip, `app.py` must be at the top level.

---

## 3. Create The S3 Buckets

Create an input bucket:

```text
pdf-pipeline-input-<account-id>-us-east-1
```

Create a results bucket:

```text
pdf-pipeline-results-<account-id>-us-east-1
```

For both buckets:

- Keep block public access enabled.
- Keep default encryption enabled.
- Use the same AWS region.

Upload `build/lambda-package.zip` to the results bucket under:

```text
deployment/lambda-package.zip
```

Copy its S3 URI or object URL.

---

## 4. Create The Lambda Function

1. Open Lambda in the AWS Console.
2. Choose **Create function**.
3. Choose **Author from scratch**.
4. Function name: `pdf-pipeline-process-pdf`.
5. Runtime: `Python 3.12`.
6. Architecture: `x86_64`.
7. Permissions: create a new role with basic Lambda permissions.
8. Create the function.

Set runtime handler:

```text
app.lambda_handler
```

Upload code:

1. Go to **Code**.
2. Choose **Upload from**.
3. Choose **Amazon S3 location**.
4. Paste the S3 URI or object URL for `deployment/lambda-package.zip`.
5. Save.

Configure:

| Setting | Value |
| --- | --- |
| Memory | `512 MB` |
| Timeout | `1 minute` |

Environment variables:

| Key | Value |
| --- | --- |
| `RESULTS_BUCKET` | `pdf-pipeline-results-<account-id>-us-east-1` |
| `LOG_LEVEL` | `INFO` |

---

## 5. Add Lambda Permissions

Open the Lambda execution role in IAM and add an inline policy.

Replace `<input-bucket>` and `<results-bucket>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadUploadedPdfs",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::<input-bucket>/*"
    },
    {
      "Sid": "WriteCsvResults",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<results-bucket>/results/*"
    }
  ]
}
```

---

## 6. Add The S3 Trigger

1. Open the Lambda function.
2. Choose **Add trigger**.
3. Trigger source: **S3**.
4. Bucket: your input bucket.
5. Event type: **All object create events**.
6. Suffix: `.pdf`.
7. Add the trigger.

This is safe because Lambda writes CSV files to a different bucket.

---

## 7. Test The Deployment

Upload one sample PDF to the input bucket:

```text
sample_pdfs/invoice_001.pdf
```

Check CloudWatch logs. You should see lines like:

```text
INFO Processing s3://pdf-pipeline-input-.../invoice_001.pdf
INFO   Category: Invoice (confidence margin: ...)
INFO   Wrote CSV sidecar: s3://pdf-pipeline-results-.../results/....csv
INFO   Done in ... ms
```

Confirm the output:

1. Open the results bucket.
2. Open the `results/` folder.
3. Download or preview the generated `.csv` file.

Expected result after uploading all six sample PDFs:

- 2 invoice CSV files
- 2 sales report CSV files
- 2 customer application CSV files

---

## 8. Common Issues

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Unable to import module 'app'` | Zip has an extra parent folder or missing files | Rebuild the zip and confirm `app.py` is at the zip root |
| `No module named pdfplumber`, `sklearn`, or `numpy` | Dependencies were not packaged | Rebuild the zip with dependencies |
| Import errors mention incompatible binaries | Dependencies were built for the wrong OS | Build with Docker using `--platform linux/amd64` |
| Lambda logs `AccessDenied` for S3 | Role cannot read input bucket or write results bucket | Recheck the inline IAM policy bucket names |
| Uploading a PDF does nothing | S3 trigger missing or suffix mismatch | Recreate the trigger with suffix `.pdf` |
| Lambda times out | PDF is large or memory is too low | Increase timeout and memory |

---

## 9. Cleanup

When finished:

1. Empty the input bucket.
2. Empty the results bucket.
3. Delete both buckets.
4. Delete the Lambda function.
5. Delete the Lambda execution role.
6. Delete the CloudWatch log group `/aws/lambda/pdf-pipeline-process-pdf`.

---

## 10. What To Show Your Evaluator

1. The Lambda function page.
2. The S3 trigger attached to Lambda.
3. CloudWatch logs from a real PDF upload.
4. CSV result files in the S3 results bucket.
5. Local test output from `python scripts/test_handler_locally.py`.
