"""
PlanTopic agent — generates a structured research plan for a topic.

Input:  topic_context dict (title, description, instructions, subtopics)
Output: research_plan dict

Model: low_capability (gpt-4o-mini) — structured output, low token volume.

Prompts are loaded from prompts.yaml — edit that file to change agent behaviour
without touching code.
"""
from __future__ import annotations

import json
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, resolve_model
from ..provider import Message

_AGENT = "planner"


def run_planner_agent(topic_context: dict) -> dict:
    """
    Generate a research plan for the given topic.

    Returns:
        {
            "search_queries": ["query 1", ...],
            "key_questions": ["What is...", ...],
            "section_outline": [{"title": "...", "scope": "..."}, ...],
            "estimated_sections": int,
        }
    """
    cfg = get_agent_config(_AGENT)
    model = resolve_model(_AGENT)

    system = Template(get_prompt(_AGENT, "system")).safe_substitute()
    user = Template(get_prompt(_AGENT, "user")).safe_substitute(
        title=topic_context["title"],
        description=topic_context.get("description", ""),
        instructions=topic_context.get("instructions", ""),
        subtopics_json=json.dumps(topic_context.get("subtopics", [])),
    )

    resp = call_llm(
        agent=_AGENT,
        messages=[Message(role="system", content=system), Message(role="user", content=user)],
        model=model,
        cfg=cfg,
        json_mode=True,
    )

    try:
        plan = json.loads(resp.content)
    except json.JSONDecodeError:
        plan = {"search_queries": [topic_context["title"]], "key_questions": [],
                "section_outline": [], "estimated_sections": 3}

    plan["_meta"] = {
        "agent": _AGENT,
        "model": resp.model,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return plan
