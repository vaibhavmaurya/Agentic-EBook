#!/usr/bin/env bash
# =============================================================================
# deploy_workers.sh — Package and deploy worker Lambda functions to AWS
#
# Usage:
#   ./scripts/deploy_workers.sh [worker_name]
#
# Examples:
#   ./scripts/deploy_workers.sh              # deploy ALL workers
#   ./scripts/deploy_workers.sh topic_loader # deploy only topic_loader
#
# Prerequisites:
#   - .env.local loaded (or AWS_* env vars set in your shell)
#   - Python venv activated (.venv at repo root)
#   - AWS CLI v2 configured with dev credentials
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/.build/workers"
ENV="${DEPLOY_ENV:-dev}"

# Map worker filename → Lambda function name (must match Terraform naming)
declare -A WORKER_FUNCTIONS=(
    ["topic_loader"]="ebook-platform-$ENV-topic-loader"
    ["topic_context_builder"]="ebook-platform-$ENV-topic-context-builder"
    ["planner_worker"]="ebook-platform-$ENV-planner-worker"
    ["research_worker"]="ebook-platform-$ENV-research-worker"
    ["verifier_worker"]="ebook-platform-$ENV-verifier-worker"
    ["artifact_persister"]="ebook-platform-$ENV-artifact-persister"
    ["draft_worker"]="ebook-platform-$ENV-draft-worker"
    ["editorial_worker"]="ebook-platform-$ENV-editorial-worker"
    ["draft_builder_worker"]="ebook-platform-$ENV-draft-builder-worker"
    ["diff_worker"]="ebook-platform-$ENV-diff-worker"
    ["approval_worker"]="ebook-platform-$ENV-approval-worker"
    ["publish_worker"]="ebook-platform-$ENV-publish-worker"
    ["search_index_worker"]="ebook-platform-$ENV-search-index-worker"
    ["digest_worker"]="ebook-platform-$ENV-digest"
)

AWS_REGION="${AWS_REGION:-us-east-1}"

TARGET="${1:-all}"

build_and_deploy() {
    local worker_name="$1"
    local function_name="${WORKER_FUNCTIONS[$worker_name]}"

    echo "── Building $worker_name → $function_name ──"

    local pkg_dir="$BUILD_DIR/$worker_name"
    rm -rf "$pkg_dir"
    mkdir -p "$pkg_dir"

    # Install runtime deps into the package dir
    pip install \
        --quiet \
        --target "$pkg_dir" \
        boto3 pydantic python-dotenv

    # Copy shared_types package
    cp -r "$REPO_ROOT/packages/shared-types" "$pkg_dir/shared_types"

    # Copy the services/workers package (base.py + the specific worker)
    mkdir -p "$pkg_dir/services/workers"
    touch "$pkg_dir/services/__init__.py"
    touch "$pkg_dir/services/workers/__init__.py"
    cp "$REPO_ROOT/services/workers/base.py" "$pkg_dir/services/workers/base.py"
    cp "$REPO_ROOT/services/workers/${worker_name}.py" "$pkg_dir/services/workers/${worker_name}.py"

    # Create Lambda handler shim: lambda_function.handler → worker handler
    cat > "$pkg_dir/lambda_function.py" << PYEOF
"""Lambda entry point shim — routes to the real worker handler."""
from services.workers.${worker_name} import handler as lambda_handler


def handler(event, context):
    return lambda_handler(event, context)
PYEOF

    # Zip it up
    local zip_path="$BUILD_DIR/${worker_name}.zip"
    (cd "$pkg_dir" && zip -r -q "$zip_path" .)

    # Deploy to Lambda
    aws lambda update-function-code \
        --function-name "$function_name" \
        --zip-file "fileb://$zip_path" \
        --region "$AWS_REGION" \
        --output text \
        --query 'FunctionName'

    echo "  ✓ $function_name deployed"
}

# ── Main ──────────────────────────────────────────────────────────────────────

mkdir -p "$BUILD_DIR"

if [[ "$TARGET" == "all" ]]; then
    for worker in "${!WORKER_FUNCTIONS[@]}"; do
        build_and_deploy "$worker"
    done
else
    if [[ -z "${WORKER_FUNCTIONS[$TARGET]+_}" ]]; then
        echo "ERROR: Unknown worker '$TARGET'. Valid workers:"
        for k in "${!WORKER_FUNCTIONS[@]}"; do echo "  $k"; done
        exit 1
    fi
    build_and_deploy "$TARGET"
fi

echo ""
echo "✓ Deployment complete."
