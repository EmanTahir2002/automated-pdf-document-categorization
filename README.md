# PDF Tagging and Summarization Pipeline

Week 03, Task 01 - AWS Internship

This project is a serverless PDF processing pipeline for digitally-native PDFs. It extracts selectable text from uploaded PDF files, identifies the business category, extracts useful metadata and normalized keyword fields, generates a short summary, and saves the final structured output as a CSV file.

The pipeline can run in two ways:

- locally, using Python scripts and sample PDFs
- on AWS, using S3, Lambda, IAM, and CloudWatch

No OCR, Textract, Bedrock, external LLM, or database is used in the current version.

## AWS Structure Used

These are the AWS resources used for this deployment:

| Resource | Name / Value |
| --- | --- |
| Input S3 bucket | `pdf-pipeline-input-eman` |
| Results S3 bucket | `pdf-pipeline-results-eman` |
| Deployment folder | `deployment/` |
| Lambda package URL | `https://pdf-pipeline-results-eman.s3.us-east-1.amazonaws.com/deployment/lambda-package.zip` |
| Lambda function | `pdf-pipeline-process-pdf` |
| Lambda handler | `app.lambda_handler` |
| Lambda role | `pdf-pipeline-process-pdf-role-dpyuatwn` |
| IAM policy | `pdf-pipeline-s3-access` |
| Output folder | `results/` inside the results bucket |

AWS flow:

```text
PDF uploaded to pdf-pipeline-input-eman
        |
        v
S3 ObjectCreated trigger for .pdf files
        |
        v
Lambda function: pdf-pipeline-process-pdf
        |
        v
PDF text extraction, classification, field extraction, summarization
        |
        v
CSV written to pdf-pipeline-results-eman/results/
        |
        v
CloudWatch logs record the execution
```

The Lambda zip is stored in the results bucket under `deployment/` because Lambda can load deployment packages from S3. The actual generated CSV outputs are stored separately under `results/`.

## Why This Architecture

S3 is used because it is simple, cheap, and event-driven. When a PDF is uploaded to the input bucket, S3 automatically triggers Lambda. Lambda is used because the PDF processing task is short-lived and does not require a running server. The results are saved as CSV in another S3 bucket so they can be downloaded, opened in Excel, or imported into another system later. The input and output buckets are separate to avoid recursive triggers, where Lambda output could accidentally trigger itself again.

## Local Pipeline

Local processing uses the same modules that run inside Lambda.

```text
PDF file
  -> text_extractor.py
  -> classifier.py
  -> metadata_extractor.py
  -> generic_field_extractor.py
  -> summarizer.py
  -> record_formatter.py
  -> local_results/<pdf-name>.csv
```

### 1. Text Extraction

`lambda_src/text_extractor.py` extracts text from digitally-native PDFs using `pdfplumber`.

This works for PDFs where text is selectable. It does not perform OCR, so scanned/image-only PDFs are outside the current scope.

### 2. Business Category Classification

`lambda_src/classifier.py` classifies documents into:

- `Invoice`
- `Sales Report`
- `Customer Application`
- `Unknown`

The classifier combines four ideas:

1. **Category aliases**  
   Predefined business phrases are checked for each category. For example, invoice-like phrases include `invoice no`, `bill to`, `amount due`, `grand total`, and `payment terms`.

2. **TF-IDF similarity**  
   The extracted PDF text is compared with prototype text for each business category. This gives a document-level similarity score based on word importance and word overlap.

3. **Structural hints**  
   The classifier checks for document patterns. For example, invoices often contain line items with `description`, `quantity`, `unit price`, and `total`. Customer applications often contain personal and employment information.

4. **Confidence threshold**  
   The best category is selected only if the score is strong enough. If the classifier is not confident, the document can be marked as `Unknown`.

This makes classification more reliable than simple keyword matching alone.

### 3. Metadata Extraction

`lambda_src/metadata_extractor.py` extracts category-specific fields. For example:

- invoices: invoice number, invoice date, due date, bill to, subtotal, tax, total amount
- sales reports: reporting period, quarter, region, total revenue
- customer applications: application ID, applicant name, date of birth, employer, annual income

### 4. Generic Keyword Extraction

`lambda_src/generic_field_extractor.py` extracts fields using aliases and synonyms.

Example:

```text
Tax
Sales Tax
GST
VAT
Tarif
Tariff
Levy
Duty
```

All of these can be normalized into the same canonical field:

```text
tax
```

So if one invoice says `GST` and another says `Tarif`, the value is still stored under `tax` instead of being skipped.

The pipeline stores:

- `keyword_fields`: clean normalized values
- `keyword_matches`: evidence showing which label was matched and what value was extracted

### 5. Summarization

`lambda_src/summarizer.py` creates a short local extractive summary. It does not call any paid AI service.

### 6. CSV Formatting

`lambda_src/record_formatter.py` creates the final CSV row. Nested fields like `metadata`, `keyword_fields`, and `keyword_matches` are stored as JSON strings inside CSV cells. This keeps the file easy to open while preserving structured data.

## Repository Structure

```text
pdf_pipeline_aws/
|-- README.md
|-- template.yaml
|-- deploy.sh
|-- docs/
|   `-- DEPLOYMENT.md
|-- lambda_src/
|   |-- app.py
|   |-- classifier.py
|   |-- generic_field_extractor.py
|   |-- metadata_extractor.py
|   |-- record_formatter.py
|   |-- requirements.txt
|   |-- summarizer.py
|   `-- text_extractor.py
|-- sample_pdfs/
|-- scripts/
|   |-- generate_sample_pdfs.py
|   |-- process_pdf_locally.py
|   `-- test_handler_locally.py
`-- .gitignore
```

`local_results/` and `build/` are generated folders and are ignored by Git.

## Run Locally

From the project folder:

```powershell
cd "D:\internship aws\week 03\task 01\files\pdf_pipeline_aws"
```

Install dependencies:

```powershell
python -m pip install -r lambda_src\requirements.txt
```

Process one PDF:

```powershell
python scripts\process_pdf_locally.py sample_pdfs\test.pdf
```

Expected output:

```text
local_results/test.csv
```

Run the full local handler simulation:

```powershell
python scripts\test_handler_locally.py
```

Expected result:

```text
PASS: all PDFs processed end-to-end through the handler.
```

You can also test individual modules:

```powershell
python lambda_src\text_extractor.py sample_pdfs\test.pdf
python lambda_src\classifier.py sample_pdfs\test.pdf
python lambda_src\metadata_extractor.py sample_pdfs\test.pdf
```

## Lambda Package Build Without Docker

The deployment package is built without Docker by downloading Linux-compatible wheels:

```powershell
cd "D:\internship aws\week 03\task 01\files\pdf_pipeline_aws"

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build\package

python -m pip install `
  --platform manylinux2014_x86_64 `
  --implementation cp `
  --python-version 3.12 `
  --only-binary=:all: `
  --target build\package `
  -r lambda_src\requirements.txt

Copy-Item lambda_src\*.py build\package\

cd build\package
Compress-Archive -Path * -DestinationPath ..\lambda-package.zip -Force
```

The generated zip is:

```text
build/lambda-package.zip
```

This zip is uploaded to:

```text
s3://pdf-pipeline-results-eman/deployment/lambda-package.zip
```

## AWS Console Steps Taken

1. Created input bucket `pdf-pipeline-input-eman`.
2. Created results bucket `pdf-pipeline-results-eman`.
3. Created a `deployment/` folder in the results bucket.
4. Uploaded `lambda-package.zip` to `deployment/lambda-package.zip`.
5. Created Lambda function `pdf-pipeline-process-pdf`.
6. Set Lambda handler to `app.lambda_handler`.
7. Created/used execution role `pdf-pipeline-process-pdf-role-dpyuatwn`.
8. Added inline IAM policy `pdf-pipeline-s3-access`.
9. Gave Lambda permission to read PDFs from the input bucket.
10. Gave Lambda permission to write CSV files to `results/` in the results bucket.
11. Added environment variable:

```text
RESULTS_BUCKET=pdf-pipeline-results-eman
```

12. Added an S3 trigger on `pdf-pipeline-input-eman` for `.pdf` uploads.
13. Uploaded `test.pdf` to the input bucket.
14. Verified that Lambda generated a CSV file in:

```text
pdf-pipeline-results-eman/results/
```

## Output CSV

Each PDF produces one CSV row with columns such as:

- `document_id`
- `filename`
- `source_bucket`
- `source_key`
- `s3_uri`
- `category`
- `best_category_match`
- `confidence`
- `num_pages`
- `char_count`
- `extractor`
- `summary`
- `metadata`
- `keyword_fields`
- `keyword_matches`
- `category_scores`
- `category_alias_scores`
- `category_tfidf_scores`
- `category_structural_scores`
- `processed_at`

Example result from AWS:

```text
test.pdf -> Invoice -> CSV saved in results bucket
```

## Notes and Limitations

- This pipeline is for digitally-native PDFs with selectable text.
- Scanned PDFs require OCR, which is not included.
- The classifier is explainable and local, not a black-box model.
- TF-IDF here is implemented locally without `scikit-learn` to keep the Lambda package small.
- CSV output stores nested structures as JSON strings inside cells.
- The current version stores results in S3 only.

## Git Push Steps

From the project folder:

```powershell
cd "D:\internship aws\week 03\task 01\files\pdf_pipeline_aws"
```

Initialize Git:

```powershell
git init
```

Check files:

```powershell
git status
```

Add files:

```powershell
git add .
```

Commit:

```powershell
git commit -m "Add serverless PDF tagging pipeline"
```

Create a new empty repository on GitHub. Do not add a README there because this project already has one.

Connect your local folder to GitHub:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
git push -u origin main
```

If Git asks you to sign in, use your GitHub login or personal access token.
