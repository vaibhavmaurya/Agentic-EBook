"""
Skeleton Lambda handler — placeholder deployed by M1 Terraform.
Real implementation is added per milestone (M2 onward).
"""
import json


def lambda_handler(event, context):
    return {
        "statusCode": 501,
        "body": json.dumps({"message": "Not implemented yet"}),
    }
