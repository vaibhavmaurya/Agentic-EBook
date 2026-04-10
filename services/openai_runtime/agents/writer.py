"""
DraftChapter agent — generates the chapter draft from validated evidence.

This is the ONLY agent that uses the high_capability model (gpt-4o).
Quality of the output directly determines what the admin reviews.

Model: high_capability (gpt-4o) — long-form content, quality-critical.

Prompts are loaded from prompts.yaml — edit that file to change the chapter
structure, length targets, citation style, or required elements without
touching code.
"""
from __future__ import annotations

import json
from pathlib import Path
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, resolve_model
from ..provider import Message

_AGENT = "writer"
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
        return "Write clearly for a professional technical audience. Use Markdown formatting."


def run_writer_agent(topic_context: dict, validated_evidence: dict) -> dict:
    """
    Draft a chapter from validated evidence.

    Returns:
        {
            "content": str,          # full Markdown chapter
            "sections": [str],       # list of H2 section headings extracted
            "word_count": int,
            "_meta": { ... }
        }
    """
    cfg = get_agent_config(_AGENT)
    model = resolve_model(_AGENT)
    style_guide = _load_style_guide()

    sources = validated_evidence.get("sources", [])
    findings = validated_evidence.get("findings", [])

    source_list = "\n".join(
        f"[{i+1}] {s['title']} — {s['url']}" for i, s in enumerate(sources[:10])
    )
    findings_json = json.dumps(findings[:15], indent=2)

    system = Template(get_prompt(_AGENT, "system")).safe_substitute(
        style_guide=style_guide,
        source_list=source_list,
    )
    user = Template(get_prompt(_AGENT, "user")).safe_substitute(
        title=topic_context["title"],
        description=topic_context.get("description", ""),
        instructions=topic_context.get("instructions", ""),
        subtopics_json=json.dumps(topic_context.get("subtopics", [])),
        findings_json=findings_json,
    )

    resp = call_llm(
        agent=_AGENT,
        messages=[Message(role="system", content=system), Message(role="user", content=user)],
        model=model,
        cfg=cfg,
    )

    content = resp.content
    sections = _extract_h2_headings(content)
    word_count = len(content.split())

    return {
        "content": content,
        "sections": sections,
        "word_count": word_count,
        "_meta": {
            "agent": _AGENT,
            "model": resp.model,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
    }


def _extract_h2_headings(content: str) -> list[str]:
    return [
        line.lstrip("# ").strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]
