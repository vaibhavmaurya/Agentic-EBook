locals {
  name_prefix        = "${var.project}-${var.env}"
  state_machine_name = "${local.name_prefix}-topic-pipeline"
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/${local.state_machine_name}"
  retention_in_days = 14
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = local.state_machine_name
  role_arn = var.sfn_execution_role_arn
  type     = "STANDARD"

  # Skeleton ASL — real state transitions implemented in M4.
  # Each state invokes its Lambda worker and passes the full execution context.
  definition = jsonencode({
    Comment = "Agentic Ebook topic pipeline — skeleton (M1)"
    StartAt = "LoadTopicConfig"
    States = {
      LoadTopicConfig = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.topic_loader_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.loader_result"
        Next           = "AssembleTopicContext"
      }

      AssembleTopicContext = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.topic_context_builder_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.context_result"
        Next           = "PlanTopic"
      }

      PlanTopic = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.planner_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.plan_result"
        Next           = "ResearchTopic"
      }

      ResearchTopic = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.research_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.research_result"
        Next           = "VerifyEvidence"
      }

      VerifyEvidence = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.verifier_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.verify_result"
        Next           = "PersistEvidenceArtifacts"
      }

      PersistEvidenceArtifacts = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.artifact_persister_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.persist_result"
        Next           = "DraftChapter"
      }

      DraftChapter = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.draft_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.draft_result"
        Next           = "EditorialReview"
      }

      EditorialReview = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.editorial_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.editorial_result"
        Next           = "BuildDraftArtifact"
      }

      BuildDraftArtifact = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.draft_builder_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.build_result"
        Next           = "GenerateDiffAndReleaseNotes"
      }

      GenerateDiffAndReleaseNotes = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.diff_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.diff_result"
        Next           = "NotifyAdminForReview"
      }

      NotifyAdminForReview = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.approval_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.notify_result"
        Next           = "WaitForApproval"
      }

      # Callback pattern — execution pauses here until SendTaskSuccess/Failure.
      # task_token comes from the context object ($$); input is the full current state ($).
      WaitForApproval = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke.waitForTaskToken"
        Parameters = {
          FunctionName = var.approval_worker_arn
          Payload = {
            "task_token.$" = "$$.Task.Token"
            "input.$"      = "$"
          }
        }
        HeartbeatSeconds = 259200  # 72 hours
        ResultPath       = "$.approval_result"
        Next             = "RouteApprovalDecision"
      }

      RouteApprovalDecision = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.approval_result.decision"
            StringEquals = "approve"
            Next         = "PublishTopic"
          },
          {
            Variable     = "$.approval_result.decision"
            StringEquals = "reject"
            Next         = "StoreRejection"
          }
        ]
        Default = "StoreRejection"
      }

      PublishTopic = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.publish_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.publish_result"
        Next           = "RebuildIndexes"
      }

      RebuildIndexes = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.search_index_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.index_result"
        Next           = "PipelineSucceeded"
      }

      StoreRejection = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = var.approval_worker_arn
          "Payload.$"  = "$"
        }
        ResultSelector = { "body.$" = "$.Payload" }
        ResultPath     = "$.rejection_result"
        Next           = "PipelineSucceeded"
      }

      PipelineSucceeded = {
        Type = "Succeed"
      }
    }
  })

  logging_configuration {
    level                  = "ERROR"
    include_execution_data = false
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
  }

  tracing_configuration {
    enabled = true
  }
}
