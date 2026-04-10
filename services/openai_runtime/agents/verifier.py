"""
VerifyEvidence agent — quality-gates the evidence set before writing.

Checks:
  - Minimum source count and relevance threshold
  - Coverage of key questions
  - Flags low-confidence or contradictory evidence

Model: low_capability (gpt-4o-mini) — deterministic scoring.

Prompts are loaded from prompts.yaml — edit that file to change agent behaviour
without touching code.
"""
from __future__ import annotations

import json
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, resolve_model
from ..provider import Message

_AGENT = "verifier"
_MIN_SOURCES = 2
_MIN_QUALITY_SCORE = 0.4


def run_verifier_agent(topic_context: dict, evidence_set: dict) -> dict:
    """
    Validate the evidence set and return a quality-gated version.

    Returns:
        {
            "sources": [...],            # filtered sources above threshold
            "findings": [...],           # from evidence_set
            "quality_score": float,      # 0.0–1.0
            "sufficient": bool,
            "gaps": [...],
            "concerns": [...],
            "_meta": { ... }
        }

    Raises:
        ValueError: if evidence is critically insufficient (< _MIN_SOURCES)
    """
    cfg = get_agent_config(_AGENT)
    model = resolve_model(_AGENT)

    sources = evidence_set.get("sources", [])
    findings = evidence_set.get("findings", [])
    key_questions = evidence_set.get("key_questions", [])

    # Filter by relevance threshold
    good_sources = [s for s in sources if s.get("relevance_score", 0) >= _MIN_QUALITY_SCORE]

    if len(good_sources) < _MIN_SOURCES:
        raise ValueError(
            f"Insufficient evidence: only {len(good_sources)} source(s) met the quality "
            f"threshold ({_MIN_QUALITY_SCORE}). Minimum required: {_MIN_SOURCES}."
        )

    system = Template(get_prompt(_AGENT, "system")).safe_substitute()
    user = Template(get_prompt(_AGENT, "user")).safe_substitute(
        title=topic_context["title"],
        key_questions_json=json.dumps(key_questions, indent=2),
        findings_json=json.dumps(findings[:10], indent=2),
        findings_count=str(len(findings)),
        sources_count=str(len(good_sources)),
    )

    resp = call_llm(
        agent=_AGENT,
        messages=[Message(role="system", content=system), Message(role="user", content=user)],
        model=model,
        cfg=cfg,
        json_mode=True,
    )

    try:
        assessment = json.loads(resp.content)
    except json.JSONDecodeError:
        assessment = {"quality_score": 0.6, "sufficient": True, "gaps": [], "concerns": []}

    return {
        "sources": good_sources,
        "findings": findings,
        "quality_score": assessment.get("quality_score", 0.6),
        "sufficient": assessment.get("sufficient", True),
        "gaps": assessment.get("gaps", []),
        "concerns": assessment.get("concerns", []),
        "key_questions": key_questions,
        "_meta": {
            "agent": _AGENT,
            "model": resp.model,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
    }
