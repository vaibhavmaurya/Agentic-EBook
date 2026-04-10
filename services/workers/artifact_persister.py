"""
PersistEvidenceArtifacts — Step Functions worker (stage 6 of 14).

Copies verified evidence to the canonical S3 artifact layout so
downstream workers have a stable read path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env.local")
except ImportError:
    pass

from services.workers.base import extract_execution_input, get_s3_json, put_s3_json
from shared_types.tracer import stage_completed, stage_started

_STAGE = "PersistEvidenceArtifacts"


def persist_artifacts(topic_id: str, run_id: str, verified_uri: str | None = None) -> dict:
    stage_started(run_id, _STAGE)

    if verified_uri:
        validated = get_s3_json(verified_uri)
        # Write the source list separately for easy inspection
        sources_uri = put_s3_json(topic_id, run_id, "extracted", "sources.json",
                                   validated.get("sources", []))
        findings_uri = put_s3_json(topic_id, run_id, "extracted", "findings.json",
                                    validated.get("findings", []))
    else:
        sources_uri = None
        findings_uri = None

    stage_completed(run_id, _STAGE, sources_uri=sources_uri, findings_uri=findings_uri)
    return {
        "topic_id": topic_id,
        "run_id": run_id,
        "sources_uri": sources_uri,
        "findings_uri": findings_uri,
        "verified_uri": verified_uri,
    }


def handler(event: dict, _context: Any) -> dict:
    inp = extract_execution_input(event)
    verify = event.get("verify_result", {}).get("body", {})
    return persist_artifacts(inp["topic_id"], inp["run_id"], verify.get("verified_uri"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--verified-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(persist_artifacts(args.topic_id, args.run_id, args.verified_uri), indent=2))
