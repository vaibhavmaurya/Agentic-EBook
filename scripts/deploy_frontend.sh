#!/usr/bin/env bash
# =============================================================================
# deploy_frontend.sh — Build and deploy frontend apps to AWS Amplify
#
# Deploys:
#   - apps/admin-site  → ebook-platform-admin-<env>  (Amplify)
#   - apps/public-site → ebook-platform-public-<env> (Amplify)
#
# Usage:
#   ./scripts/deploy_frontend.sh           # deploy both
#   ./scripts/deploy_frontend.sh admin     # admin SPA only
#   ./scripts/deploy_frontend.sh public    # public site only
#
# Prerequisites:
#   - Node.js 20+ installed
#   - AWS CLI v2 configured
#   - .env.local loaded (for PUBLIC_API_BASE_URL, etc.)
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV="${DEPLOY_ENV:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
TARGET="${1:-both}"

# ── Amplify app IDs (from terraform output / aws cli) ────────────────────────
get_app_id() {
    local app_name="$1"
    aws amplify list-apps \
        --query "apps[?name=='$app_name'].appId" \
        --output text \
        --region "$AWS_REGION"
}

ADMIN_APP_NAME="ebook-platform-admin-$ENV"
PUBLIC_APP_NAME="ebook-platform-public-$ENV"

# ── Deploy a built dist/ folder to Amplify via manual deployment ──────────────
deploy_to_amplify() {
    local app_name="$1"
    local dist_dir="$2"
    local branch="$ENV"

    local app_id
    app_id=$(get_app_id "$app_name")

    if [[ -z "$app_id" ]]; then
        echo "  ✗ Could not find Amplify app: $app_name"
        return 1
    fi

    echo "  App ID: $app_id  Branch: $branch"

    # Create a manual deployment slot
    local deploy_json
    deploy_json=$(aws amplify create-deployment \
        --app-id "$app_id" \
        --branch-name "$branch" \
        --region "$AWS_REGION" \
        --output json)

    local job_id zip_url
    job_id=$(echo "$deploy_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['jobId'])")
    zip_url=$(echo "$deploy_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['zipUploadUrl'])")

    # Zip the dist directory (using Python for cross-platform compatibility)
    local zip_path="/tmp/${app_name}-deploy.zip"
    python3 "$REPO_ROOT/scripts/zipdir.py" "$dist_dir" "$zip_path"
    echo "  Zipped dist → $zip_path"

    # Upload to the pre-signed S3 URL
    curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X PUT \
        -H "Content-Type: application/zip" \
        --data-binary "@$zip_path" \
        "$zip_url" || true
    echo ""

    # Start the deployment
    aws amplify start-deployment \
        --app-id "$app_id" \
        --branch-name "$branch" \
        --job-id "$job_id" \
        --region "$AWS_REGION" \
        --output text \
        --query 'jobSummary.status'

    echo "  Waiting for deployment to complete…"
    local status="PENDING"
    local attempts=0
    while [[ "$status" != "SUCCEED" && "$status" != "FAILED" && $attempts -lt 30 ]]; do
        sleep 10
        status=$(aws amplify get-job \
            --app-id "$app_id" \
            --branch-name "$branch" \
            --job-id "$job_id" \
            --region "$AWS_REGION" \
            --query 'job.summary.status' \
            --output text)
        echo "  Status: $status"
        ((attempts++))
    done

    if [[ "$status" == "SUCCEED" ]]; then
        echo "  ✓ Deployed: https://$branch.$app_id.amplifyapp.com"
    else
        echo "  ✗ Deployment ended with status: $status"
        return 1
    fi
}

# ── Build and deploy Admin SPA ────────────────────────────────────────────────
deploy_admin() {
    echo ""
    echo "── Admin SPA ──────────────────────────────────────────────────────────"

    # Get API URL from API Gateway
    local api_url
    api_url=$(aws apigatewayv2 get-apis \
        --query "Items[?contains(Name,'ebook-platform-$ENV')].ApiEndpoint" \
        --output text --region "$AWS_REGION")

    local cognito_pool_id cognito_client_id
    cognito_pool_id=$(aws cognito-idp list-user-pools --max-results 10 \
        --query "UserPools[?contains(Name,'ebook-platform')].Id" \
        --output text --region "$AWS_REGION")
    cognito_client_id=$(aws cognito-idp list-user-pool-clients \
        --user-pool-id "$cognito_pool_id" \
        --query "UserPoolClients[0].ClientId" \
        --output text --region "$AWS_REGION")

    echo "  API URL: $api_url"
    echo "  Cognito Pool: $cognito_pool_id"

    cd "$REPO_ROOT/apps/admin-site"
    npm install --silent

    # Write env file for Vite build
    cat > .env.production << EOF
VITE_API_BASE_URL=$api_url
VITE_COGNITO_USER_POOL_ID=$cognito_pool_id
VITE_COGNITO_CLIENT_ID=$cognito_client_id
EOF

    npm run build
    deploy_to_amplify "$ADMIN_APP_NAME" "$REPO_ROOT/apps/admin-site/dist"
    rm -f .env.production
}

# ── Build and deploy Public Astro site ───────────────────────────────────────
deploy_public() {
    echo ""
    echo "── Public Site ────────────────────────────────────────────────────────"

    local api_url
    api_url=$(aws apigatewayv2 get-apis \
        --query "Items[?contains(Name,'ebook-platform-$ENV')].ApiEndpoint" \
        --output text --region "$AWS_REGION")

    echo "  API URL: $api_url"

    cd "$REPO_ROOT/apps/public-site"
    npm install --silent

    # Write env file for Astro build
    cat > .env << EOF
PUBLIC_API_BASE_URL=$api_url
AWS_REGION=$AWS_REGION
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
S3_ARTIFACT_BUCKET=${S3_ARTIFACT_BUCKET:-ebook-platform-artifacts-$ENV}
EOF

    npm run build
    rm -f .env

    # Save dist zip to S3 so search_index_worker can trigger a redeploy after publish
    local zip_path="/tmp/public-site-latest.zip"
    python3 "$REPO_ROOT/scripts/zipdir.py" "$REPO_ROOT/apps/public-site/dist" "$zip_path"
    S3_BUCKET="${S3_ARTIFACT_BUCKET:-ebook-platform-artifacts-$ENV}"
    aws s3 cp "$zip_path" "s3://$S3_BUCKET/deployments/public-site.zip" \
        --region "$AWS_REGION" --no-progress
    echo "  Saved dist zip to s3://$S3_BUCKET/deployments/public-site.zip"

    deploy_to_amplify "$PUBLIC_APP_NAME" "$REPO_ROOT/apps/public-site/dist"
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "$TARGET" in
    admin)  deploy_admin ;;
    public) deploy_public ;;
    both)   deploy_admin; deploy_public ;;
    *)      echo "Usage: $0 [admin|public|both]"; exit 1 ;;
esac

echo ""
echo "✓ Frontend deployment complete."
