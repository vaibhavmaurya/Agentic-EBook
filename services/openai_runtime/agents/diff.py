"""
GenerateDiff agent — produces a human-readable change summary vs. the prior version.

If there is no prior published version, returns a first-publish summary.

Model: low_capability (gpt-4o-mini) — structured comparison, low token volume.

Prompts are loaded from prompts.yaml — edit that file to change the release
notes format without touching code.
"""
from __future__ import annotations

import json
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, resolve_model
from ..provider import Message

_AGENT = "diff"


def run_diff_agent(topic_context: dict, new_draft: dict, prior_content: str | None = None) -> dict:
    """
    Compare the new draft against the prior published version.

    Args:
        topic_context:  topic metadata
        new_draft:      output of run_editor_agent (has 'content' key)
        prior_content:  Markdown text of the prior published chapter, or None

    Returns:
        {
            "is_first_version": bool,
            "sections_added": [str],
            "sections_removed": [str],
            "sections_changed": [str],
            "release_notes": str,        # 2–4 sentence summary for readers
            "_meta": { ... }
        }
    """
    cfg = get_agent_config(_AGENT)
    model = resolve_model(_AGENT)

    new_content = new_draft.get("content", "")

    if not prior_content:
        system = Template(get_prompt(_AGENT, "first_version_system")).safe_substitute()
        user = Template(get_prompt(_AGENT, "first_version_user")).safe_substitute(
            title=topic_context["title"],
            new_content_preview=new_content[:1000],
            sections_json=json.dumps(new_draft.get("sections", [])),
        )
    else:
        system = Template(get_prompt(_AGENT, "incremental_system")).safe_substitute()
        user = Template(get_prompt(_AGENT, "incremental_user")).safe_substitute(
            title=topic_context["title"],
            prior_content_preview=prior_content[:1500],
            new_content_preview=new_content[:1500],
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
    except json.JSONDecodeError:
        if not prior_content:
            result = {
                "is_first_version": True,
                "sections_added": new_draft.get("sections", []),
                "sections_removed": [],
                "sections_changed": [],
                "release_notes": f"Initial publication of the {topic_context['title']} chapter.",
            }
        else:
            result = {
                "is_first_version": False,
                "sections_added": [],
                "sections_removed": [],
                "sections_changed": new_draft.get("sections", []),
                "release_notes": f"Updated content for {topic_context['title']}.",
            }

    result["_meta"] = {
        "agent": _AGENT,
        "model": resp.model,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return result
