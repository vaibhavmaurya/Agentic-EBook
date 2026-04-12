"""
LLM Configuration management API.

Routes (API Gateway HTTP API payload format 2.0):
  GET  /admin/config/models   — read model_config.yaml from S3 (returns JSON)
  PUT  /admin/config/models   — write model_config.yaml to S3
  GET  /admin/config/prompts  — read prompts.yaml from S3 (returns JSON)
  PUT  /admin/config/prompts  — write prompts.yaml to S3

Storage: s3://<S3_ARTIFACT_BUCKET>/config/model_config.yaml
                                   /config/prompts.yaml

Fallback: if the S3 key does not exist, the bundled local YAML is returned.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3
import yaml

# ── Constants ─────────────────────────────────────────────────────────────────

_S3_BUCKET = os.environ.get("S3_ARTIFACT_BUCKET", "")
_AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")

_S3_MODELS_KEY = "config/model_config.yaml"
_S3_PROMPTS_KEY = "config/prompts.yaml"

# Paths to the bundled fallback YAML files (relative to this file when deployed,
# resolved dynamically so they work both locally and in Lambda).
_HERE = Path(__file__).parent
_OPENAI_RUNTIME_DIR = _HERE.parent / "openai_runtime"
_LOCAL_MODELS_PATH = _OPENAI_RUNTIME_DIR / "model_config.yaml"
_LOCAL_PROMPTS_PATH = _OPENAI_RUNTIME_DIR / "prompts.yaml"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _s3():
    return boto3.client("s3", region_name=_AWS_REGION)


def _ok(body: Any, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _err(message: str, status: int = 400) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "ConfigError", "message": message}),
    }


def _read_yaml_from_s3(key: str, fallback_path: Path) -> dict:
    """Read YAML from S3; fall back to the bundled local file if absent."""
    if _S3_BUCKET:
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return yaml.safe_load(resp["Body"].read()) or {}
        except Exception as exc:  # noqa: BLE001
            print(f"[config_api] S3 read error for {key}: {exc}")

    if fallback_path.exists():
        with open(fallback_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _read_yaml_from_s3_safe(key: str, fallback_path: Path) -> dict:
    """Same as _read_yaml_from_s3 but catches all S3 errors gracefully."""
    if _S3_BUCKET:
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return yaml.safe_load(resp["Body"].read()) or {}
        except Exception as exc:  # noqa: BLE001
            print(f"[config_api] S3 read error for {key}: {exc}")

    if fallback_path.exists():
        with open(fallback_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _write_yaml_to_s3(key: str, data: dict) -> None:
    """Serialize dict back to YAML and write to S3."""
    if not _S3_BUCKET:
        raise RuntimeError("S3_ARTIFACT_BUCKET is not configured")
    yaml_bytes = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).encode()
    _s3().put_object(
        Bucket=_S3_BUCKET,
        Key=key,
        Body=yaml_bytes,
        ContentType="text/yaml",
    )


# ── Route handlers ────────────────────────────────────────────────────────────

def get_model_config() -> dict:
    data = _read_yaml_from_s3_safe(_S3_MODELS_KEY, _LOCAL_MODELS_PATH)
    return _ok({"config": data, "source": "s3" if _S3_BUCKET else "local"})


def put_model_config(body_str: str | None) -> dict:
    if not body_str:
        return _err("Request body is required")
    try:
        payload = json.loads(body_str)
        config = payload.get("config", payload)  # accept {config: {...}} or the dict directly
    except (json.JSONDecodeError, ValueError) as exc:
        return _err(f"Invalid JSON: {exc}")

    # Basic structural validation
    if not isinstance(config, dict):
        return _err("Config must be a JSON object")
    if "active_provider" not in config:
        return _err("Missing required field: active_provider")
    if "agents" not in config:
        return _err("Missing required field: agents")

    try:
        _write_yaml_to_s3(_S3_MODELS_KEY, config)
    except Exception as exc:
        return _err(f"Failed to save config: {exc}", 500)

    return _ok({"message": "Model config saved. Workers will pick up changes on next cold start.", "config": config})


def get_prompts_config() -> dict:
    data = _read_yaml_from_s3_safe(_S3_PROMPTS_KEY, _LOCAL_PROMPTS_PATH)
    return _ok({"config": data, "source": "s3" if _S3_BUCKET else "local"})


def put_prompts_config(body_str: str | None) -> dict:
    if not body_str:
        return _err("Request body is required")
    try:
        payload = json.loads(body_str)
        config = payload.get("config", payload)
    except (json.JSONDecodeError, ValueError) as exc:
        return _err(f"Invalid JSON: {exc}")

    if not isinstance(config, dict):
        return _err("Prompts config must be a JSON object")

    try:
        _write_yaml_to_s3(_S3_PROMPTS_KEY, config)
    except Exception as exc:
        return _err(f"Failed to save prompts: {exc}", 500)

    return _ok({"message": "Prompts config saved. Workers will pick up changes on next cold start.", "config": config})


# ── Lambda entry point ────────────────────────────────────────────────────────

def lambda_handler(event: dict, context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    path = event.get("rawPath", "")
    body = event.get("body")

    if path == "/admin/config/models":
        if method == "GET":
            return get_model_config()
        if method == "PUT":
            return put_model_config(body)
        return _err("Method not allowed", 405)

    if path == "/admin/config/prompts":
        if method == "GET":
            return get_prompts_config()
        if method == "PUT":
            return put_prompts_config(body)
        return _err("Method not allowed", 405)

    return _err("Not found", 404)
