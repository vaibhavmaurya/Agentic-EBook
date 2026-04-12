#!/usr/bin/env bash
# =============================================================================
# deploy_public_site.sh — Build the Astro public site and deploy to Amplify
#
# Usage:
#   ./scripts/deploy_public_site.sh
#
# Prerequisites:
#   - .env.local loaded (or env vars set in shell)
#   - Node.js + npm installed
#   - Python venv activated (.venv at repo root)
#   - AWS credentials configured
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_DIR="$REPO_ROOT/apps/public-site"
BUILD_DIR="$REPO_ROOT/.build"
ZIP_PATH="$BUILD_DIR/public-site.zip"

AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${S3_ARTIFACT_BUCKET:-ebook-platform-artifacts-dev}"
AMPLIFY_APP_ID="${AMPLIFY_APP_ID:-djcvgu9ysuar}"
AMPLIFY_BRANCH="${AMPLIFY_BRANCH:-dev}"

echo "── Building public site ──"
cd "$SITE_DIR"
npm run build

echo "── Zipping dist ──"
mkdir -p "$BUILD_DIR"
python3 "$REPO_ROOT/scripts/zipdir.py" "$SITE_DIR/dist" "$ZIP_PATH"

echo "── Uploading zip to S3 ──"
local_zip_path=$(cygpath -w "$ZIP_PATH" 2>/dev/null || echo "$ZIP_PATH")
aws s3 cp "$local_zip_path" "s3://$S3_BUCKET/deployments/public-site.zip" \
    --region "$AWS_REGION" --no-progress

echo "── Deploying to Amplify ──"
PYTHON="${REPO_ROOT}/.venv/Scripts/python"
[ -f "$PYTHON" ] || PYTHON="$(command -v python3)"
"$PYTHON" - << 'PYEOF'
import boto3, os, urllib.request, sys

region = os.environ.get("AWS_REGION", "us-east-1")
s3_bucket = os.environ.get("S3_ARTIFACT_BUCKET", "ebook-platform-artifacts-dev")
app_id = os.environ.get("AMPLIFY_APP_ID", "djcvgu9ysuar")
branch = os.environ.get("AMPLIFY_BRANCH", "dev")

amplify = boto3.client("amplify", region_name=region)
s3 = boto3.client("s3", region_name=region)

# Fetch the zip from S3
zip_data = s3.get_object(Bucket=s3_bucket, Key="deployments/public-site.zip")["Body"].read()
print(f"  zip size: {len(zip_data)} bytes")

# Stop any pending deployments first
try:
    jobs = amplify.list_jobs(appId=app_id, branchName=branch)
    for j in jobs.get("jobSummaries", []):
        if j.get("status") == "PENDING":
            amplify.stop_job(appId=app_id, branchName=branch, jobId=j["jobId"])
            print(f"  stopped pending job {j['jobId']}")
except Exception as e:
    print(f"  warning: {e}")

# Create deployment
resp = amplify.create_deployment(appId=app_id, branchName=branch)
job_id = resp["jobId"]
zip_url = resp["zipUploadUrl"]

# Upload
req = urllib.request.Request(zip_url, data=zip_data, method="PUT")
req.add_header("Content-Type", "application/zip")
urllib.request.urlopen(req)

# Start
amplify.start_deployment(appId=app_id, branchName=branch, jobId=job_id)
print(f"  Deployment started: jobId={job_id}")
print(f"  URL: https://{branch}.{amplify.get_app(appId=app_id)['app']['defaultDomain']}")
PYEOF

echo ""
echo "✓ Public site deployed."
