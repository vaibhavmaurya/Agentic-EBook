"""
ResearchTopic agent — fetches evidence from the web for a given research plan.

Flow (no unbounded agentic loop — fixed-cost pipeline):
  1. Deterministic: execute web searches
  2. Deterministic: fetch + extract content from top URLs
  3. Deterministic: score sources
  4. LLM call: synthesize evidence into structured findings

Model: low_capability (gpt-4o-mini) — high token volume; quality from tools.

Prompts are loaded from prompts.yaml — edit that file to change agent behaviour
without touching code.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from string import Template

from .._agent_base import call_llm
from ..config import get_agent_config, get_prompt, load_config, resolve_model
from ..provider import Message
from ..tools.fetch_url import fetch_url
from ..tools.score_source import score_source
from ..tools.web_search import web_search

_AGENT = "research"


def run_research_agent(topic_context: dict, research_plan: dict) -> dict:
    """
    Execute the research plan and return an evidence set.

    Returns:
        {
            "sources": [
                {
                    "url": str,
                    "title": str,
                    "content": str,      # truncated to max_source_chars
                    "relevance_score": float,
                    "fetched_at": str,
                }
            ],
            "findings": [...],
            "coverage_gaps": [...],
            "key_questions": [...],
            "search_queries_used": [...],
            "total_sources": int,
            "_meta": { agent, model, input_tokens, output_tokens }
        }
    """
    agent_cfg = get_agent_config(_AGENT)
    rt_cfg = load_config().research_tools
    model = resolve_model(_AGENT)

    queries: list[str] = research_plan.get("search_queries", [topic_context["title"]])
    queries = queries[:agent_cfg.max_search_queries]

    # ── Resolve search API keys from Secrets Manager if configured ────────────
    bing_key = _maybe_fetch_secret(rt_cfg.web_search.bing_secret_name)
    serpapi_key = _maybe_fetch_secret(rt_cfg.web_search.serpapi_secret_name)

    # ── Step 1: Execute web searches ──────────────────────────────────────────
    seen_urls: set[str] = set()
    candidates = []
    for q in queries:
        results = web_search(
            q,
            num_results=rt_cfg.web_search.results_per_query,
            bing_api_key=bing_key,
            serpapi_key=serpapi_key,
        )
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                candidates.append(r)

    # ── Step 2: Fetch and extract content ─────────────────────────────────────
    topic_keywords = _extract_keywords(topic_context)
    sources = []
    for candidate in candidates:
        if len(sources) >= agent_cfg.max_sources:
            break
        page = fetch_url(
            candidate.url,
            timeout_sec=rt_cfg.fetch_url.timeout_sec,
            max_content_bytes=rt_cfg.fetch_url.max_content_bytes,
            user_agent=rt_cfg.fetch_url.user_agent,
        )
        if not page or len(page.text.strip()) < 200:
            continue

        relevance = score_source(page.url, page.text, topic_keywords)
        truncated = page.text[:agent_cfg.max_source_chars]

        sources.append({
            "url": page.url,
            "title": page.title or candidate.title,
            "content": truncated,
            "relevance_score": relevance,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    # Sort by relevance descending
    sources.sort(key=lambda s: s["relevance_score"], reverse=True)

    # ── Step 3: LLM synthesis — extract structured findings from raw text ──────
    if sources:
        sources_text = "\n\n---\n\n".join(
            f"Source [{i+1}]: {s['title']}\nURL: {s['url']}\n{s['content'][:2000]}"
            for i, s in enumerate(sources[:6])
        )

        system = Template(get_prompt(_AGENT, "synthesis_system")).safe_substitute()
        user = Template(get_prompt(_AGENT, "synthesis_user")).safe_substitute(
            title=topic_context["title"],
            key_questions_json=json.dumps(research_plan.get("key_questions", []), indent=2),
            sources_text=sources_text,
        )

        resp = call_llm(
            agent=_AGENT,
            messages=[Message(role="system", content=system), Message(role="user", content=user)],
            model=model,
            cfg=agent_cfg,
            json_mode=True,
        )
        try:
            synthesis = json.loads(resp.content)
        except json.JSONDecodeError:
            synthesis = {"findings": [], "coverage_gaps": []}

        meta = {
            "agent": _AGENT,
            "model": resp.model,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
    else:
        synthesis = {"findings": [], "coverage_gaps": ["No sources found."]}
        meta = {"agent": _AGENT, "model": model, "input_tokens": 0, "output_tokens": 0}

    return {
        "sources": sources,
        "findings": synthesis.get("findings", []),
        "coverage_gaps": synthesis.get("coverage_gaps", []),
        "key_questions": research_plan.get("key_questions", []),
        "search_queries_used": queries,
        "total_sources": len(sources),
        "_meta": meta,
    }


def _extract_keywords(topic_context: dict) -> list[str]:
    words = topic_context["title"].split() + topic_context.get("subtopics", [])
    return [w.strip(",.") for w in words if len(w) > 3]


def _maybe_fetch_secret(secret_name: str) -> str | None:
    if not secret_name:
        return None
    try:
        import boto3
        import json as _json
        sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        raw = sm.get_secret_value(SecretId=secret_name)["SecretString"]
        try:
            return _json.loads(raw)["api_key"]
        except Exception:
            return raw.strip()
    except Exception:
        return None
