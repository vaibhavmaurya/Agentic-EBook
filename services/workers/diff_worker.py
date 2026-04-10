"""
GenerateDiffAndReleaseNotes — Step Functions worker (stage 10 of 14).
Implemented in M4.
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

_STAGE = "GenerateDiffAndReleaseNotes"


def handler(event: dict, context: Any) -> dict:
    inp = extract_execution_input(event)
    run_id = inp["run_id"]
    stage_started(run_id, _STAGE, agent_name="diff")
    # TODO M4: call openai_runtime.run_diff_agent(prior_version, new_draft)
    result = {"topic_id": inp["topic_id"], "run_id": run_id, "diff_summary_uri": None, "status": "STUB"}
    stage_completed(run_id, _STAGE, agent_name="diff", model_name="gpt-4o-mini")
    return result
