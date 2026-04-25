# SOP 07 — Security Controls

## Purpose

Security controls that cannot be verified automatically must be checked manually. This SOP defines the non-negotiable controls and provides concrete verification steps for each.

---

## Secret Management

### The Only Acceptable Pattern

| Secret type | Where it lives | How it's accessed |
|---|---|---|
| OpenAI API key | AWS Secrets Manager | `boto3` `get_secret_value()` at Lambda cold start |
| AWS credentials (local dev) | `.env.local` (gitignored) | Environment variables, picked up by `boto3` automatically |
| AWS credentials (Lambda) | IAM role attached to function | No credentials needed — role provides identity |
| Cognito pool/client IDs | Environment variables (safe — not secrets) | `process.env.VITE_COGNITO_*` in frontend |
| Database connection strings | AWS Secrets Manager | `get_secret_value()` at startup |

### What You Must Never Do

- Never store the OpenAI API key in a Lambda environment variable — it appears in CloudWatch logs on startup and in the Lambda console to anyone with `lambda:GetFunctionConfiguration`
- Never commit `.env.local` — add it to `.gitignore` before the first commit
- Never hardcode credentials in source code — even in comments or test files
- Never use your personal AWS root account credentials — create IAM users or roles with least-privilege

### Secrets Manager Access Pattern

```python
import boto3, json

def get_openai_key() -> str:
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=os.environ["OPENAI_SECRET_NAME"])
    secret = json.loads(response["SecretString"])
    return secret["api_key"]

# Cache at module level (cold start fetches once per Lambda instance)
_OPENAI_KEY = None

def get_cached_openai_key() -> str:
    global _OPENAI_KEY
    if _OPENAI_KEY is None:
        _OPENAI_KEY = get_openai_key()
    return _OPENAI_KEY
```

Caching at module level avoids a Secrets Manager API call on every Lambda invocation. One call per cold start.

---

## API Authorization

### All `/admin/*` Routes Must Have JWT Auth

Every admin endpoint must be protected by the Cognito JWT authorizer at the API Gateway level — not just in application code. Defense in depth: even if application code has a bug, the authorizer blocks unauthenticated requests before the Lambda is invoked.

**Terraform verification:**
```hcl
# Every admin route must specify the authorizer
resource "aws_apigatewayv2_route" "admin_topics" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "ANY /admin/{proxy+}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Public routes explicitly have NO authorizer
resource "aws_apigatewayv2_route" "public_topics" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "ANY /public/{proxy+}"
  authorization_type = "NONE"  # ← explicit
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
```

**Verification test (run after every deployment):**
```bash
# Should return 401 — no token
curl -s -o /dev/null -w "%{http_code}" \
  https://your-api.execute-api.us-east-1.amazonaws.com/admin/topics
# Expected: 401

# Should return 200 — public route
curl -s -o /dev/null -w "%{http_code}" \
  https://your-api.execute-api.us-east-1.amazonaws.com/public/toc
# Expected: 200
```

### Cognito Token Validation

JWT validation is handled by API Gateway. You do not need to validate JWTs in Lambda code for routes protected by the authorizer. But do validate that the user is in the correct group for admin operations:

```python
def require_admin(event: dict):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    groups = claims.get("cognito:groups", "").split(",")
    if "ebook-admins" not in groups:
        raise PermissionError("Requires ebook-admins group membership")
```

---

## S3 Bucket Security

### Block Public Access (Always)

All S3 buckets must have `BlockPublicAccess` enabled. Public site content is served through Amplify Hosting CDN — never directly from S3.

```hcl
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**Verification:**
```bash
aws s3api get-public-access-block --bucket ebook-platform-artifacts-dev
# All four values must be: true
```

### Bucket Policies

No bucket policy should allow `Principal: "*"`. All access is via IAM roles attached to Lambda functions.

---

## IAM Least Privilege

### Per-Function Roles

Every Lambda function gets its own IAM role. No shared roles.

**Verification:**
```bash
# List all Lambda functions and their roles
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `ebook`)].{Name: FunctionName, Role: Role}' --output table
# Each function should have a unique role name
```

### No Wildcard Actions in Prod

In dev, `Resource: "*"` is acceptable temporarily to unblock development. Before production:

1. Run `aws iam simulate-principal-policy` to identify which specific resources each Lambda actually needs
2. Replace `"*"` with specific ARNs for each resource
3. Run a full end-to-end test after tightening policies

```bash
# Find any wildcard resource policies
aws iam list-role-policies --role-name ebook-api-lambda-role-dev --output text | \
  xargs -I {} aws iam get-role-policy --role-name ebook-api-lambda-role-dev --policy-name {}
# Look for "Resource": "*" — acceptable in dev, must be scoped in prod
```

---

## Reader Input Security

### All Submitted Content Gets `moderation_status = PENDING`

Comments and highlights submitted by readers must never be displayed to other readers without admin review.

```python
# In public.py handler for POST /public/comments
table.put_item(Item={
    "PK": f"TOPIC#{topic_id}",
    "SK": f"FEEDBACK#{feedback_id}",
    "content": comment_text,
    "moderation_status": "PENDING",  # ← always pending on creation
    "created_at": datetime.utcnow().isoformat(),
})
```

The feedback summary endpoint in the admin API shows all comments. The public-facing display should only show `moderation_status == "APPROVED"` items (future Phase 2 moderation UI).

### Input Validation

```python
MAX_COMMENT_LENGTH = 2000
MAX_HIGHLIGHT_LENGTH = 500

def validate_comment(text: str):
    if not text or len(text.strip()) == 0:
        raise ValueError("Comment cannot be empty")
    if len(text) > MAX_COMMENT_LENGTH:
        raise ValueError(f"Comment exceeds {MAX_COMMENT_LENGTH} character limit")
    # Strip HTML tags
    return re.sub(r'<[^>]+>', '', text).strip()
```

### Rate Limiting

Enable rate limiting on all public write endpoints at the API Gateway level:

```hcl
resource "aws_apigatewayv2_stage" "default" {
  # ...
  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 10  # requests per second
  }
}
```

Apply tighter limits to write endpoints (`/public/comments`, `/public/highlights`) than read endpoints.

---

## CORS Configuration

### Dev: Allow All Origins

```hcl
cors_configuration {
  allow_origins = ["*"]
  allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allow_headers = ["Content-Type", "Authorization"]
  max_age       = 300
}
```

### Prod: Restrict to Known Origins

```hcl
cors_configuration {
  allow_origins = [
    "https://your-public-site.amplifyapp.com",
    "https://your-admin-site.amplifyapp.com",
    "https://www.your-domain.com"
  ]
  # ...
}
```

Never ship to production with `allow_origins = ["*"]`.

---

## Encryption

All data must be encrypted at rest and in transit.

| Resource | Encryption |
|---|---|
| DynamoDB | SSE enabled (AWS managed key) |
| S3 | SSE-S3 enabled on all buckets |
| Secrets Manager | KMS encryption (AWS managed key) |
| API Gateway | HTTPS only (enforced by AWS) |
| Amplify Hosting | HTTPS only (enforced by AWS) |
| Lambda environment variables | Encrypted at rest by AWS KMS |
| CloudWatch Logs | Encrypted by default |

**Terraform enforcement:**
```hcl
resource "aws_dynamodb_table" "main" {
  # ...
  server_side_encryption {
    enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
```

---

## Pre-Production Security Checklist

```
[ ] terraform plan shows no public S3 buckets or open security groups
[ ] All /admin/* routes tested with no token → 401
[ ] All /admin/* routes tested with valid token → 200
[ ] No .env.local committed: git log --all --full-history -- .env.local
[ ] No API keys in Lambda environment variables: aws lambda get-function-configuration --function-name X | grep -i key
[ ] OpenAI secret in Secrets Manager: aws secretsmanager describe-secret --secret-id ebook-platform/openai-key
[ ] S3 public access blocked on all buckets
[ ] IAM wildcard resources reviewed and scoped
[ ] Input validation on all public write endpoints
[ ] Rate limiting enabled on public write endpoints
[ ] moderation_status=PENDING on all reader-submitted content
[ ] CORS restricted to specific origins (not *)
```
