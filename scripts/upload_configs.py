#!/usr/bin/env python3
"""
upload_configs.py — Upload LLM configuration files to S3.

Usage:
  python scripts/upload_configs.py [--bucket BUCKET] [--region REGION]

Files uploaded:
  services/openai_runtime/model_config.yaml  →  s3://<bucket>/config/model_config.yaml
  services/openai_runtime/prompts.yaml       →  s3://<bucket>/config/prompts.yaml

At runtime, workers automatically load from S3 if S3_ARTIFACT_BUCKET is set,
so changes to model_config.yaml or prompts.yaml take effect on the next Lambda
invocation without requiring a Lambda redeployment.

To force S3 loading only (skip local file fallback), set:
  MODEL_CONFIG_PATH=s3://<bucket>/config/model_config.yaml
  PROMPTS_CONFIG_PATH=s3://<bucket>/config/prompts.yaml
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

import boto3

_FILES = [
    ("services/openai_runtime/model_config.yaml", "config/model_config.yaml"),
    ("services/openai_runtime/prompts.yaml",       "config/prompts.yaml"),
]


def upload_configs(bucket: str, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    for local_rel, s3_key in _FILES:
        local_path = _REPO_ROOT / local_rel
        if not local_path.exists():
            print(f"  SKIP  {local_rel} (not found)")
            continue
        s3.upload_file(
            str(local_path),
            bucket,
            s3_key,
            ExtraArgs={"ContentType": "text/yaml"},
        )
        print(f"  OK    s3://{bucket}/{s3_key}")


def main() -> None:
    default_bucket = os.environ.get("S3_ARTIFACT_BUCKET", "ebook-platform-artifacts-dev")
    default_region = os.environ.get("AWS_REGION", "us-east-1")

    parser = argparse.ArgumentParser(description="Upload LLM config files to S3.")
    parser.add_argument("--bucket", default=default_bucket, help="S3 bucket name")
    parser.add_argument("--region", default=default_region, help="AWS region")
    args = parser.parse_args()

    print(f"Uploading configs to s3://{args.bucket}/config/")
    upload_configs(args.bucket, args.region)
    print("Done. Changes take effect on the next Lambda invocation.")


if __name__ == "__main__":
    main()
