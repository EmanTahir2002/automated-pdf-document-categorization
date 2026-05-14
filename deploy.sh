#!/usr/bin/env bash
#
# deploy.sh — One-command build, deploy, and smoke-test for the pipeline.
#
# Prerequisites:
#   - AWS CLI v2 configured (aws configure)  → run `aws sts get-caller-identity` to verify
#   - SAM CLI installed                       → run `sam --version` to verify
#   - Docker running (sam build uses it)      → run `docker ps` to verify
#
# Usage:
#   ./deploy.sh                  # first-time deploy with guided prompts
#   ./deploy.sh --quick          # subsequent deploys without prompts
#
# The first deploy will ask you for stack name, region, etc. Accept the
# defaults unless you have a reason to change them. After the first
# deploy, samconfig.toml saves your answers so future `sam deploy` calls
# pick them up automatically.

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="pdf-pipeline"

echo "================================================================"
echo "  PDF Tagging & Summarization Pipeline — Deploy"
echo "  Region: $REGION   Stack: $STACK_NAME"
echo "================================================================"

# Sanity checks
command -v aws  >/dev/null || { echo "ERROR: aws CLI not installed"; exit 1; }
command -v sam  >/dev/null || { echo "ERROR: sam CLI not installed (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)"; exit 1; }
command -v docker >/dev/null || { echo "ERROR: docker not installed (sam build --use-container needs it)"; exit 1; }

if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured. Run: aws configure"
  exit 1
fi

# -------------------------------------------------------------------
# Build — uses a Docker container that matches Lambda's runtime exactly,
# so native deps (numpy, scikit-learn) get the right Linux wheels.
# -------------------------------------------------------------------
echo ""
echo "[1/3] Building Lambda package (this takes ~2-3 minutes the first time)..."
sam build --use-container

# -------------------------------------------------------------------
# Deploy
# -------------------------------------------------------------------
echo ""
echo "[2/3] Deploying to AWS..."
if [[ "${1:-}" == "--quick" ]] || [[ -f samconfig.toml ]]; then
  sam deploy --no-confirm-changeset
else
  sam deploy --guided \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3
fi

# -------------------------------------------------------------------
# Verify — read outputs from the stack and print useful next steps
# -------------------------------------------------------------------
echo ""
echo "[3/3] Reading stack outputs..."
INPUT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`InputBucketName`].OutputValue' --output text)
TABLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`DocumentsTableName`].OutputValue' --output text)
LOG_GROUP=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaLogGroup`].OutputValue' --output text)

echo ""
echo "================================================================"
echo "  Deploy complete."
echo "================================================================"
echo ""
echo "  Input bucket:  $INPUT_BUCKET"
echo "  DynamoDB:      $TABLE"
echo "  Logs:          $LOG_GROUP"
echo ""
echo "  Test with one of the sample PDFs:"
echo ""
echo "    aws s3 cp sample_pdfs/invoice_001.pdf s3://$INPUT_BUCKET/ --region $REGION"
echo ""
echo "  Then watch the Lambda logs in real time:"
echo ""
echo "    sam logs -n ProcessPdfFunction --stack-name $STACK_NAME --tail"
echo ""
echo "  And query the DynamoDB table:"
echo ""
echo "    python scripts/query_documents.py --table $TABLE --region $REGION list"
echo ""
