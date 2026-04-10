"""
EditorialReview agent — applies topic-specific instructions and style checks to the draft.

Uses the topic's own `instructions` field as the editorial rubric, so the admin's
intent is enforced automatically without hardcoding editorial rules.

Model: low_capability (gpt-4o-mini) — checklist-based edits, lower token cost.

Prompts are loaded from prompts.yaml — edit that file to change the editorial
criteria, scoring dimensions, or output format without touching code.
"""
from __future__ import annotations

import json
from pathlib import Path
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, resolve_model
from ..provider import Message

_AGENT = "editor"
_STYLE_GUIDE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "packages"
    / "prompt-policies"
    / "style_guide.md"
)


def _load_style_guide() -> str:
    try:
        return _STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def run_editor_agent(topic_context: dict, draft_content: dict) -> dict:
    """
    Review and improve the draft. Returns the edited draft and a scorecard.

    Returns:
        {
            "content": str,             # edited Markdown chapter
            "scorecard": {
                "instruction_adherence": float,   # 0–1
                "style_compliance": float,
                "factual_confidence": float,
                "clarity": float,
                "overall": float,
            },
            "changes_summary": str,
            "word_count": int,
            "_meta": { ... }
        }
    """
    cfg = get_agent_config(_AGENT)
    model = resolve_model(_AGENT)
    style_guide = _load_style_guide()

    original = draft_content.get("content", "")
    instructions = topic_context.get("instructions", "")

    system = Template(get_prompt(_AGENT, "system")).safe_substitute(
        style_guide=style_guide,
        instructions=instructions,
    )
    user = Template(get_prompt(_AGENT, "user")).safe_substitute(
        draft_content=original,
    )

    resp = call_llm(
        agent=_AGENT,
        messages=[Message(role="system", content=system), Message(role="user", content=user)],
        model=model,
        cfg=cfg,
        json_mode=True,
    )

    try:
        result = json.loads(resp.content)
        content = result.get("content", original)
        scorecard = result.get("scorecard", {})
        changes_summary = result.get("changes_summary", "")
    except json.JSONDecodeError:
        content = original
        scorecard = {}
        changes_summary = "Editor output could not be parsed; original draft preserved."

    for key in ("instruction_adherence", "style_compliance", "factual_confidence", "clarity", "overall"):
        scorecard.setdefault(key, 0.7)

    return {
        "content": content,
        "scorecard": scorecard,
        "changes_summary": changes_summary,
        "word_count": len(content.split()),
        "_meta": {
            "agent": _AGENT,
            "model": resp.model,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
    }
