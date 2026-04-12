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
S3_BUCKET="${S3_ARTIFACT_BUCKET:-ebook-platform-artifacts-$ENV}"

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

# Workers that call AI agents and need openai_runtime + openai package
AI_WORKERS=(
    "planner_worker"
    "research_worker"
    "verifier_worker"
    "draft_worker"
    "editorial_worker"
    "diff_worker"
)

is_ai_worker() {
    local name="$1"
    for w in "${AI_WORKERS[@]}"; do
        [[ "$w" == "$name" ]] && return 0
    done
    return 1
}

build_and_deploy() {
    local worker_name="$1"
    local function_name="${WORKER_FUNCTIONS[$worker_name]}"

    echo "── Building $worker_name → $function_name ──"

    local pkg_dir="$BUILD_DIR/$worker_name"
    rm -rf "$pkg_dir"
    mkdir -p "$pkg_dir"

    # Install runtime deps — boto3 is excluded (provided by Lambda Python 3.12 runtime)
    # Force manylinux wheels — Lambda runs Linux, dev machine may be Windows.
    pip install \
        --quiet \
        --target "$pkg_dir" \
        --platform manylinux2014_x86_64 \
        --python-version 3.12 \
        --only-binary=:all: \
        --implementation cp \
        pydantic python-dotenv

    # AI workers also need:
    #   openai httpx pyyaml — LLM runtime
    #   duckduckgo-search requests beautifulsoup4 — research tools (web search + URL fetch)
    if is_ai_worker "$worker_name"; then
        pip install \
            --quiet \
            --target "$pkg_dir" \
            --platform manylinux2014_x86_64 \
            --python-version 3.12 \
            --only-binary=:all: \
            --implementation cp \
            openai httpx pyyaml ddgs requests beautifulsoup4
    fi

    # Copy shared_types package
    cp -r "$REPO_ROOT/packages/shared-types" "$pkg_dir/shared_types"

    # Copy the services/workers package (base.py + the specific worker)
    mkdir -p "$pkg_dir/services/workers"
    touch "$pkg_dir/services/__init__.py"
    touch "$pkg_dir/services/workers/__init__.py"
    cp "$REPO_ROOT/services/workers/base.py" "$pkg_dir/services/workers/base.py"
    cp "$REPO_ROOT/services/workers/${worker_name}.py" "$pkg_dir/services/workers/${worker_name}.py"

    # AI workers also need the full openai_runtime module.
    # Workers import it as "services.openai_runtime" so it must live at services/openai_runtime/.
    if is_ai_worker "$worker_name"; then
        cp -r "$REPO_ROOT/services/openai_runtime" "$pkg_dir/services/openai_runtime"
        # Also copy prompt_policies used by Writer/Editor agents
        if [[ -d "$REPO_ROOT/packages/prompt-policies" ]]; then
            mkdir -p "$pkg_dir/packages/prompt-policies"
            cp -r "$REPO_ROOT/packages/prompt-policies/." "$pkg_dir/packages/prompt-policies/"
        fi
    fi

    # Create Lambda handler shim — Terraform configured handler = "handler.lambda_handler"
    cat > "$pkg_dir/handler.py" << PYEOF
"""Lambda entry point shim — routes to the real worker handler."""
from services.workers.${worker_name} import handler as _worker_handler


def lambda_handler(event, context):
    return _worker_handler(event, context)
PYEOF

    # Zip it up (using Python for cross-platform compatibility)
    local zip_path="$BUILD_DIR/${worker_name}.zip"
    python3 "$REPO_ROOT/scripts/zipdir.py" "$pkg_dir" "$zip_path"

    # Upload to S3 then deploy (avoids direct-upload timeouts on slow connections)
    local s3_key="deployments/${worker_name}.zip"
    local win_zip_path
    win_zip_path=$(cygpath -w "$zip_path" 2>/dev/null || echo "$zip_path")
    aws s3 cp "$win_zip_path" "s3://$S3_BUCKET/$s3_key" --region "$AWS_REGION" --no-progress

    aws lambda update-function-code \
        --function-name "$function_name" \
        --s3-bucket "$S3_BUCKET" \
        --s3-key "$s3_key" \
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
