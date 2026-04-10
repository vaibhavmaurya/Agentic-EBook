# AGENTS.md — openai_runtime Module

This document describes the design, configuration, and extension points of the
`services/openai_runtime/` module — the **only** place in the codebase that
may import an LLM SDK.

---

## Overview

All six AI agents in the pipeline are implemented here. Every other module
(workers, API handlers, notebooks) calls the public functions exposed in
`__init__.py`:

```python
from services.openai_runtime import (
    run_planner_agent,
    run_research_agent,
    run_verifier_agent,
    run_writer_agent,
    run_editor_agent,
    run_diff_agent,
)
```

Changing the active provider or swapping a model requires **only a YAML edit** —
no code changes anywhere.

---

## Directory Layout

```
services/openai_runtime/
  __init__.py              Public API — imports all six run_* functions
  model_config.yaml        Central model + provider configuration
  config.py                Typed config loader (lru_cached, reads YAML once)
  provider.py              LLMProvider Protocol, get_provider() factory
  _agent_base.py           call_llm() shared by all agents
  adapters/
    openai_adapter.py      OpenAI Responses API (REAL implementation)
    anthropic_adapter.py   Anthropic Claude (stub — ready to implement)
    gemini_adapter.py      Google Gemini (stub — ready to implement)
  agents/
    planner.py             Research plan generation
    research.py            Web search + evidence collection
    verifier.py            Evidence quality gate
    writer.py              Chapter drafting (HIGH capability)
    editor.py              Editorial review + scorecard
    diff.py                Release notes + change summary
  tools/
    web_search.py          DuckDuckGo / Bing / SerpAPI search
    fetch_url.py           HTTP page fetcher
    extract_content.py     HTML → clean Markdown text
    score_source.py        Deterministic source quality scorer
  requirements.txt         Python dependencies for this module
  AGENTS.md                This file
```

---

## Model Configuration (`model_config.yaml`)

### Switching providers

Change one line to route all agents through a different LLM backend:

```yaml
active_provider: openai      # ← change to "anthropic" or "gemini"
```

No other file needs to change.

### Switching models within a provider

Every agent has a `capability` key (`high` or `low`) that maps to the
provider's configured model IDs:

```yaml
providers:
  openai:
    models:
      high: gpt-4o-2024-11-20        # quality-critical agents
      low:  gpt-4o-mini-2024-07-18   # cost-optimised agents
```

To test with a specific model for one agent without changing the tier, use
`model_override`:

```yaml
agents:
  writer:
    capability: high
    model_override: gpt-4o-2024-08-06   # overrides capability lookup
```

### Agent capability assignments

| Agent | Capability | Rationale |
|---|---|---|
| `planner` | low | Structured JSON output; short context |
| `research` | low | 2 LLM calls max; synthesis from retrieved text |
| `verifier` | low | Checklist logic; low token volume |
| **`writer`** | **high** | Full chapter drafting; quality-critical |
| `editor` | low | Checklist-based edits against instructions |
| `diff` | low | Structured comparison; short context |

**Estimated cost saving vs all-high-capability:** ~80%
(5 of 6 agents use the cheaper model; the writer is the only expensive call.)

### Cost estimation

Each agent call returns `_meta.input_tokens` and `_meta.output_tokens`.
Workers pass these to `estimate_cost_usd(agent, input_tokens, output_tokens)`
which reads the provider's pricing from `model_config.yaml` and writes
`cost_usd` to the trace event in DynamoDB.

```yaml
providers:
  openai:
    pricing:
      gpt-4o-mini-2024-07-18:
        input_per_1m:  0.15
        output_per_1m: 0.60
      gpt-4o-2024-11-20:
        input_per_1m:  2.50
        output_per_1m: 10.00
```

Update these values when OpenAI changes their pricing — nothing else needs to
change.

---

## Provider Abstraction

### Adding Anthropic support

1. Open `adapters/anthropic_adapter.py`.
2. Uncomment the implementation (uses `anthropic` SDK).
3. Add `anthropic>=0.25` to `requirements.txt`.
4. Set `active_provider: anthropic` in `model_config.yaml`.
5. Fill in the model IDs under `providers.anthropic.models`.

### Adding Gemini support

Same pattern — `adapters/gemini_adapter.py` contains the stub.

### Provider contract

Any adapter must implement the `LLMProvider` Protocol from `provider.py`:

```python
class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[Message],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: list[ToolDefinition] | None,
        json_mode: bool,
    ) -> LLMResponse: ...
```

---

## Research Pipeline (no unbounded loops)

The `research` agent uses a **fixed-step pipeline** rather than an agentic
tool-use loop. This keeps token cost and latency predictable.

```
1. Planner output (search_queries, key_questions)
2. For each query → web_search() → top N URLs
3. Deduplicate URLs
4. For each URL → fetch_url() → extract_content() → score_source()
5. Keep top-K sources by score
6. LLM call 1: refine search if coverage gaps detected   [optional]
7. LLM call 2: synthesise evidence from all source text
```

Maximum: **2 LLM calls** per research run.

### Search fallback chain

`web_search()` tries providers in priority order:

1. **Bing Search API** — if `BING_API_KEY` env var is set
2. **SerpAPI** — if `SERPAPI_KEY` env var is set
3. **DuckDuckGo** (`duckduckgo-search` package) — no API key required

For local development, DuckDuckGo works out of the box with no credentials.

### Source scoring (`score_source.py`)

Scores are 0.0–1.0, computed without an LLM call:

| Component | Max | Signal |
|---|---|---|
| Domain authority | 0.35 | Known high-authority domains |
| Content richness | 0.35 | Text length + keyword coverage |
| URL quality | 0.30 | HTTPS, short query string |

Sources below **0.4** are filtered out by the verifier agent before drafting.

---

## Local Development

### Prerequisites

```bash
pip install -r services/openai_runtime/requirements.txt
```

### API key

For local testing, set `OPENAI_API_KEY` directly in `.env.local`:

```
OPENAI_API_KEY=sk-...
```

In Lambda, the key is fetched from AWS Secrets Manager at runtime
(`OPENAI_SECRET_NAME` env var, default `ebook-platform/openai-key`).

### Run a single agent in isolation

```bash
source .env.local
python services/workers/planner_worker.py \
    --topic-id <id> \
    --run-id test-$(date +%s)

python services/workers/research_worker.py \
    --topic-id <id> --run-id <run_id> \
    --plan-uri s3://ebook-platform-artifacts-dev/topics/<id>/runs/<run_id>/plan/research_plan.json

python services/workers/draft_worker.py \
    --topic-id <id> --run-id <run_id> \
    --verified-uri s3://...
```

Each worker prints the JSON result and writes its S3 artifact. The next
worker in the chain reads from that URI.

### Override the config path (for testing)

```bash
MODEL_CONFIG_PATH=/tmp/test_config.yaml python services/workers/planner_worker.py ...
```

---

## Trace Events

Every agent call records three DynamoDB trace events (via `shared_types.tracer`):

| Event | Written when | Key fields |
|---|---|---|
| `STAGE_STARTED` | Top of handler | `agent_name` |
| `STAGE_COMPLETED` | On success | `model_name`, `cost_usd`, agent-specific metrics |
| `STAGE_FAILED` | On exception | `error_message`, `error_classification` |

Run history and per-stage cost is visible in the Admin UI run detail page.

---

## Adding a New Agent

1. Add a new file `agents/<name>.py` following the pattern of `planner.py`.
2. Export `run_<name>_agent()` from `__init__.py`.
3. Add the agent config block to `model_config.yaml`:
   ```yaml
   agents:
     <name>:
       capability: low
       max_tokens: 2000
       temperature: 0.3
       timeout_sec: 60
   ```
4. Create a worker in `services/workers/<name>_worker.py`.
5. Add the state to the Step Functions state machine definition.
