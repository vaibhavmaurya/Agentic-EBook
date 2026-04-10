"""
Public API Lambda handler — implemented in M7.

Routes:
  POST /public/comments
  POST /public/highlights
  GET  /public/releases/latest
"""
import json


def lambda_handler(event: dict, context) -> dict:
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "NOT_IMPLEMENTED", "message": "Public API implemented in M7."}),
    }
