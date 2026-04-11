###############################################################################
# Agentic Ebook Platform V3 — Dev Environment
# M1-S1: Root composition — wires all 13 modules together.
#
# Modules are implemented incrementally (M1-S3 through M1-S14).
# Skeleton modules return empty outputs until implemented.
###############################################################################

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local backend for initial dev. Migrate to S3 backend before team use:
  #
  # backend "s3" {
  #   bucket         = "ebook-platform-tfstate-<account_id>"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "ebook-platform-tfstate-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

###############################################################################
# Locals — pre-computed ARNs to break circular module dependencies
###############################################################################

locals {
  name_prefix        = "${var.project}-${var.env}"
  state_machine_name = "${local.name_prefix}-topic-pipeline"

  # Pre-computed SFN ARN so IAM module can reference it without depending on
  # the step_functions module output (which would create a circular dependency).
  state_machine_arn = "arn:aws:states:${var.aws_region}:${var.aws_account_id}:stateMachine:${local.state_machine_name}"
}

###############################################################################
# Layer 1 — Leaf modules (no inter-module dependencies)
###############################################################################

module "dynamodb" {
  source  = "../../modules/dynamodb"
  env     = var.env
  project = var.project
}

module "s3_artifacts" {
  source  = "../../modules/s3_artifacts"
  env     = var.env
  project = var.project
}

module "secrets_manager" {
  source  = "../../modules/secrets_manager"
  env     = var.env
  project = var.project
}

module "cognito" {
  source  = "../../modules/cognito"
  env     = var.env
  project = var.project
}

###############################################################################
# Layer 2 — IAM (depends on layer-1 ARNs + pre-computed SFN ARN)
###############################################################################

module "iam" {
  source = "../../modules/iam"

  env            = var.env
  project        = var.project
  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id

  dynamodb_table_arn   = module.dynamodb.table_arn
  s3_bucket_arn        = module.s3_artifacts.bucket_arn
  openai_secret_arn    = module.secrets_manager.secret_arn
  state_machine_arn    = local.state_machine_arn
  ses_sender_email     = var.ses_sender_email
}

###############################################################################
# Layer 3 — Lambda functions (depends on IAM roles + data layer)
###############################################################################

module "lambda_functions" {
  source = "../../modules/lambda_functions"

  env        = var.env
  project    = var.project
  aws_region = var.aws_region

  dynamodb_table_name  = module.dynamodb.table_name
  s3_bucket_name       = module.s3_artifacts.bucket_name
  openai_secret_name   = module.secrets_manager.secret_name
  state_machine_arn    = local.state_machine_arn

  api_lambda_role_arn    = module.iam.api_lambda_role_arn
  worker_lambda_role_arn = module.iam.worker_lambda_role_arn
  digest_lambda_role_arn = module.iam.digest_lambda_role_arn
}

###############################################################################
# Layer 4 — Step Functions (depends on IAM execution role + Lambda ARNs)
###############################################################################

module "step_functions" {
  source = "../../modules/step_functions"

  env     = var.env
  project = var.project

  sfn_execution_role_arn = module.iam.sfn_execution_role_arn

  # Pipeline stage Lambda ARNs
  topic_loader_arn           = module.lambda_functions.topic_loader_arn
  topic_context_builder_arn  = module.lambda_functions.topic_context_builder_arn
  planner_worker_arn         = module.lambda_functions.planner_worker_arn
  research_worker_arn        = module.lambda_functions.research_worker_arn
  verifier_worker_arn        = module.lambda_functions.verifier_worker_arn
  artifact_persister_arn     = module.lambda_functions.artifact_persister_arn
  draft_worker_arn           = module.lambda_functions.draft_worker_arn
  editorial_worker_arn       = module.lambda_functions.editorial_worker_arn
  draft_builder_worker_arn   = module.lambda_functions.draft_builder_worker_arn
  diff_worker_arn            = module.lambda_functions.diff_worker_arn
  approval_worker_arn        = module.lambda_functions.approval_worker_arn
  publish_worker_arn         = module.lambda_functions.publish_worker_arn
  search_index_worker_arn    = module.lambda_functions.search_index_worker_arn
}

###############################################################################
# Layer 5 — API Gateway (depends on Cognito + API Lambda ARN)
###############################################################################

module "api_gateway" {
  source = "../../modules/api_gateway"

  env     = var.env
  project = var.project

  cognito_user_pool_arn = module.cognito.user_pool_arn
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_client_id     = module.cognito.client_id

  api_handler_arn  = module.lambda_functions.api_handler_arn
  api_handler_name = module.lambda_functions.api_handler_name
}

###############################################################################
# Layer 5 — EventBridge Scheduler (depends on IAM scheduler role)
###############################################################################

module "eventbridge_scheduler" {
  source = "../../modules/eventbridge_scheduler"

  env     = var.env
  project = var.project

  scheduler_role_arn     = module.iam.scheduler_role_arn
  state_machine_arn      = local.state_machine_arn
  digest_lambda_arn      = module.lambda_functions.digest_worker_arn
  digest_lambda_role_arn = module.iam.digest_lambda_role_arn
}

###############################################################################
# Layer 5 — SES (depends on IAM digest Lambda role)
###############################################################################

module "ses" {
  source = "../../modules/ses"

  env              = var.env
  project          = var.project
  ses_sender_email = var.ses_sender_email
  owner_email      = var.owner_email

  digest_lambda_role_arn = module.iam.digest_lambda_role_arn
}

###############################################################################
# Layer 6 — Monitoring (depends on API GW, SFN, Lambda names)
###############################################################################

module "monitoring" {
  source = "../../modules/monitoring"

  env            = var.env
  project        = var.project
  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id

  api_id            = module.api_gateway.api_id
  state_machine_arn = local.state_machine_arn
  alarm_email       = var.alarm_email

  worker_function_names = module.lambda_functions.worker_function_names
}

###############################################################################
# Layer 6 — Amplify apps (depend on API GW endpoint + Cognito IDs)
###############################################################################

module "amplify_public_site" {
  source = "../../modules/amplify_public_site"

  env          = var.env
  project      = var.project
  api_endpoint = module.api_gateway.api_endpoint
}

module "amplify_admin_site" {
  source = "../../modules/amplify_admin_site"

  env          = var.env
  project      = var.project
  api_endpoint = module.api_gateway.api_endpoint

  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_client_id    = module.cognito.client_id
}
