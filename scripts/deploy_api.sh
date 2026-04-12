#!/usr/bin/env bash
# =============================================================================
# deploy_api.sh — Package and deploy the API Lambda function to AWS
#
# Usage:
#   ./scripts/deploy_api.sh
#
# Notes:
#   - boto3 is excluded (provided by the Lambda Python 3.12 runtime)
#   - fastapi/uvicorn excluded (local dev only — not needed in Lambda)
#   - Deploys via S3 to handle larger packages reliably
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/.build/api"
ENV="${DEPLOY_ENV:-dev}"
FUNCTION_NAME="ebook-platform-$ENV-api"
AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${S3_ARTIFACT_BUCKET:-ebook-platform-artifacts-$ENV}"

echo "── Building API Lambda → $FUNCTION_NAME ──"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Only install deps NOT provided by the Lambda Python 3.12 runtime.
# boto3 is already in the runtime — including it would bloat the package 10x.
# Force manylinux wheels — Lambda runs Linux, dev machine may be Windows.
pip install --quiet --target "$BUILD_DIR" \
    --platform manylinux2014_x86_64 \
    --python-version 3.12 \
    --only-binary=:all: \
    --implementation cp \
    pydantic python-dotenv pyyaml

# Copy shared_types package
cp -r "$REPO_ROOT/packages/shared-types" "$BUILD_DIR/shared_types"

# Copy all API handler modules
for f in topics.py reviews.py public.py feedback.py config_api.py; do
    cp "$REPO_ROOT/services/api/$f" "$BUILD_DIR/$f"
done

# Bundle default LLM config YAMLs so config_api.py has a local fallback
mkdir -p "$BUILD_DIR/openai_runtime"
cp "$REPO_ROOT/services/openai_runtime/model_config.yaml" "$BUILD_DIR/openai_runtime/model_config.yaml"
cp "$REPO_ROOT/services/openai_runtime/prompts.yaml" "$BUILD_DIR/openai_runtime/prompts.yaml"

# Lambda entry point — Terraform configured handler = "handler.lambda_handler"
cat > "$BUILD_DIR/handler.py" << 'PYEOF'
"""Lambda entry point for the unified API handler."""
from __future__ import annotations
from typing import Any

from topics import lambda_handler as topics_handler
from reviews import lambda_handler as reviews_handler
from public import lambda_handler as public_handler
from feedback import lambda_handler as feedback_handler
from config_api import lambda_handler as config_handler


_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
}


def lambda_handler(event: dict, context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "").upper()
    path = event.get("rawPath", "")

    # Handle CORS preflight — return 200 with CORS headers immediately
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS_HEADERS, "body": ""}

    if path.startswith("/admin/config/"):
        return config_handler(event, context)
    if "/review" in path:
        return reviews_handler(event, context)
    if path.startswith("/admin/feedback") or path.endswith("/feedback"):
        return feedback_handler(event, context)
    if path.startswith("/public/"):
        return public_handler(event, context)
    return topics_handler(event, context)
PYEOF

# Zip
ZIP_PATH="$BUILD_DIR/api.zip"
python3 "$REPO_ROOT/scripts/zipdir.py" "$BUILD_DIR" "$ZIP_PATH"

# Upload to S3 then update Lambda (avoids direct-upload timeouts on slow connections)
S3_KEY="deployments/api.zip"
echo "  Uploading to s3://$S3_BUCKET/$S3_KEY …"
WIN_ZIP=$(cygpath -w "$ZIP_PATH" 2>/dev/null || echo "$ZIP_PATH")
aws s3 cp "$WIN_ZIP" "s3://$S3_BUCKET/$S3_KEY" --region "$AWS_REGION" --no-progress

aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --s3-bucket "$S3_BUCKET" \
    --s3-key "$S3_KEY" \
    --region "$AWS_REGION" \
    --output text \
    --query 'FunctionName'

echo "  ✓ $FUNCTION_NAME deployed"
echo ""
echo "✓ API deployment complete."
