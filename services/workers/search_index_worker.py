"""
RebuildIndexes — Step Functions worker (stage 14 of 14).
Implemented in M6.
"""
from __future__ import annotations

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

from services.workers.base import extract_execution_input
from shared_types.tracer import stage_completed, stage_started

_STAGE = "RebuildIndexes"


def handler(event: dict, context: Any) -> dict:
    inp = extract_execution_input(event)
    run_id = inp["run_id"]
    stage_started(run_id, _STAGE)
    # TODO M6: rebuild Lunr.js index + TOC from all published topics, write to S3
    stage_completed(run_id, _STAGE)
    return {"topic_id": inp["topic_id"], "run_id": run_id, "index_uri": None, "toc_uri": None, "status": "STUB"}
