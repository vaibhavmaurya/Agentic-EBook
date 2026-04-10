"""
Weekly Digest worker — invoked by EventBridge Scheduler (M9).
Not a Step Functions worker — runs as a standalone Lambda triggered weekly.
Implemented in M9.
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


def handler(event: dict, context: Any) -> dict:
    # TODO M9: query DDB for TOPIC_PUBLISHED events in last 7 days,
    #          assemble email body, send via SES, write NOTIF record
    return {"status": "STUB", "topics_included": 0}
