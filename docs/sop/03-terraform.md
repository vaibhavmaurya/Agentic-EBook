# SOP 03 — Terraform Best Practices

## Purpose

Terraform is the foundation. Errors here cascade into every subsequent milestone. This SOP captures the module structure, dependency management, and runtime boundary decisions that made a 83-resource infrastructure deployable in one session.

---

## Module Structure

### One Module Per AWS Resource Group

Don't create one giant Terraform module. Don't create one module per AWS service. The right granularity is **one module per logical resource group** — a set of resources that are always created/destroyed together and have no reason to exist independently.

**This project's module breakdown:**
```
modules/
  dynamodb/           ← table + GSIs (always together)
  s3_artifacts/       ← artifact bucket + lifecycle rules
  iam/                ← ALL IAM roles + policies (centralized)
  secrets_manager/    ← secret placeholders
  cognito/            ← user pool + app client + groups
  api_gateway/        ← HTTP API + JWT authorizer + routes + logging
  lambda_functions/   ← ALL Lambda functions (one module, not one per function)
  step_functions/     ← state machine + IAM + logging
  eventbridge_scheduler/ ← schedule group + IAM role
  ses/                ← email identity + send policy
  monitoring/         ← CloudWatch alarms + SNS + dashboard
  amplify_public_site/ ← public Amplify app
  amplify_admin_site/  ← admin Amplify app
```

**Why `iam/` is one centralized module:** IAM roles reference Lambda function ARNs (Lambda needs to know its role ARN), and the Lambda module needs IAM role ARNs. This creates a circular dependency. Centralizing IAM breaks the circle — IAM takes ARNs as inputs and outputs role ARNs that Lambda consumes.

### Environment Composition Pattern

```
envs/
  dev/
    main.tf       ← calls all modules with dev variable values
    variables.tf
    outputs.tf
    terraform.tfvars  ← gitignored (has real account IDs, names)
    terraform.tfvars.example  ← committed template
  prod/
    main.tf
    ...
```

Both environments call the same modules. Variables control sizing, retention, alarm thresholds. This is cheaper than duplicating module code and guarantees dev/prod parity.

---

## The Skeleton-First Pattern

**Never write a Terraform module by filling in all resources immediately.** Instead:

1. Write all module `variables.tf`, `outputs.tf`, and a skeleton `main.tf` (with commented-out resources or empty resources) for every module first
2. Run `terraform init && terraform validate` — fix any interface errors
3. Then fill in module implementations one at a time
4. Run `terraform plan` after each module to catch issues early

**Why this matters:** if you write 13 modules in one go and then run `terraform plan`, you'll face 40 errors from circular dependencies and interface mismatches all at once. Skeleton-first means each module validates independently before you wire them together.

---

## The Circular Dependency Problem

**The problem:** Lambda functions need IAM role ARNs. IAM policies need Lambda function ARNs. Terraform won't allow Module A to output something that Module A depends on from Module B.

**Solution: locals for ARN construction**

Construct expected ARNs from known patterns in the root `main.tf` using `locals`, then pass them to both modules:

```hcl
locals {
  # Construct Lambda ARNs before the Lambda module is created
  # Pattern: arn:aws:lambda:<region>:<account>:function:<name>
  lambda_api_arn = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:ebook-api-handler-${var.environment}"
}

module "iam" {
  source           = "../../modules/iam"
  lambda_api_arn   = local.lambda_api_arn
  # ... other ARNs
}

module "lambda_functions" {
  source              = "../../modules/lambda_functions"
  api_lambda_role_arn = module.iam.api_lambda_role_arn
  # ...
}
```

This breaks the cycle because `locals` are computed from variables + data sources — not from module outputs.

---

## What Belongs in Terraform vs Runtime

**This is the most important architectural boundary decision.**

### In Terraform (platform primitives — change rarely)

- DynamoDB table and GSIs
- S3 buckets, lifecycle rules
- IAM roles and base policies
- Cognito user pools, app clients, groups
- API Gateway HTTP API, JWT authorizer, base routes
- Lambda function definitions (skeleton handlers)
- Step Functions state machine
- EventBridge Scheduler **group** (not individual schedules)
- CloudWatch log groups, alarms, dashboards
- Amplify app definitions
- Secrets Manager placeholders

### At Runtime (dynamic — change frequently)

- Per-topic EventBridge Scheduler entries — created/updated/deleted by the API on every topic create/update/delete
- Topic configuration in DynamoDB
- S3 content artifacts
- Per-run DynamoDB records

**Rule of thumb:** if a resource's lifecycle is tied to a user action (create a topic, publish content), it belongs at runtime. If it exists regardless of user actions (the table that stores topics), it belongs in Terraform.

---

## Using `terraform apply -target` Safely

After initial deployment, you'll need to patch IAM policies or environment variables without rebuilding the whole environment. Use `-target` to apply changes to specific resources only.

```bash
# Add a missing IAM policy without touching other resources
terraform apply -target=module.iam.aws_iam_role_policy.api_lambda_policy

# Update a Lambda function's environment variables
terraform apply -target=module.lambda_functions.aws_lambda_function.api_handler
```

**Warning:** Amplify app resources are particularly dangerous. Terraform may want to replace (destroy + create) the Amplify app if certain attributes change. Always inspect the plan carefully:

```bash
terraform plan -target=module.amplify_public_site
# Look for "will be destroyed" — if you see it, stop and investigate
```

If Terraform wants to replace an Amplify app, it will also destroy all existing deployments. Use `-target` to update only the safe attributes (environment variables, IAM) without triggering replacement.

---

## IAM Policies — Least Privilege Patterns

### Lambda Basic Execution (always required)

```hcl
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
```

### DynamoDB Access (scoped to specific table)

```hcl
resource "aws_iam_role_policy" "dynamodb_access" {
  role = aws_iam_role.lambda_role.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
        "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchWriteItem"
      ]
      Resource = [
        var.dynamodb_table_arn,
        "${var.dynamodb_table_arn}/index/*"
      ]
    }]
  })
}
```

**Include `/index/*` if you query GSIs.** Forgetting this causes `AccessDeniedException` on GSI queries even when the table itself is accessible.

### Secrets Manager Access (scoped to specific secret)

```hcl
Statement = [{
  Effect   = "Allow"
  Action   = ["secretsmanager:GetSecretValue"]
  Resource = var.openai_secret_arn  # NOT "*"
}]
```

### Step Functions Execution Role (invoke specific Lambdas)

```hcl
Statement = [{
  Effect   = "Allow"
  Action   = ["lambda:InvokeFunction"]
  Resource = [for arn in var.worker_lambda_arns : arn]
}]
```

---

## State Management

### Backend Configuration

Use remote state from day one. Local state causes problems the moment more than one person or machine touches the infrastructure.

```hcl
terraform {
  backend "s3" {
    bucket         = "terraform-state-<account-id>"
    key            = "ebook-platform/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

### Preventing State Drift

State drift happens when someone makes a manual AWS console change that isn't reflected in Terraform. After fixing an IAM gap via AWS CLI, always:

1. Add the fix to the Terraform module
2. Run `terraform plan` to verify Terraform wants to make the same change (or no change if you've already applied)
3. Run `terraform apply` to reconcile state

**Never leave manual changes unrecorded in Terraform.** Drift accumulates and eventually a full `terraform apply` overwrites your manual patches.

---

## Terraform Workflow

```bash
# 1. Format all files
terraform fmt -recursive

# 2. Validate syntax + schema
terraform validate

# 3. Plan (always save the plan)
terraform plan -out=tfplan

# 4. Review plan — look for unexpected destroys/replacements
terraform show tfplan

# 5. Apply
terraform apply tfplan

# 6. After apply — run integration tests against the new resources
```

**Never apply without reviewing the plan.** "destroy/create" for an Amplify app or DynamoDB table destroys your data.

---

## Common Terraform Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Circular dependency | `Error: Cycle: module.a → module.b → module.a` | Extract shared ARNs to `locals` in root |
| Amplify app replacement | `aws_amplify_app.X must be replaced` | Use `-target` to update only safe attributes |
| Missing GSI IAM | `AccessDeniedException` on GSI query | Add `/index/*` to DynamoDB resource ARNs |
| Lambda function replacement | `aws_lambda_function.X must be replaced` | Usually caused by changing `filename` or `source_code_hash` |
| State lock | `Error acquiring state lock` | Check if another apply is running; use `terraform force-unlock` only if confirmed stale |
| Provider version drift | `Error: Invalid resource type` | Pin provider versions in `terraform { required_providers {} }` |
