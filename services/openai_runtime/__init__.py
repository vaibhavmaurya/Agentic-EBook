"""
openai_runtime — the ONLY module permitted to import the OpenAI (or any LLM) SDK.

All other services call the public functions exposed here.
Changing `active_provider` in model_config.yaml swaps the entire LLM backend
without touching any other code.

Public interface:
  run_planner_agent(topic_context)              -> research_plan dict
  run_research_agent(topic_context, plan)       -> evidence_set dict
  run_verifier_agent(topic_context, evidence)   -> validated_evidence dict
  run_writer_agent(topic_context, evidence)     -> draft_content dict
  run_editor_agent(topic_context, draft)        -> final_draft dict
  run_diff_agent(topic_context, new_draft)      -> diff_summary dict
"""
from .agents.planner import run_planner_agent
from .agents.research import run_research_agent
from .agents.verifier import run_verifier_agent
from .agents.writer import run_writer_agent
from .agents.editor import run_editor_agent
from .agents.diff import run_diff_agent

__all__ = [
    "run_planner_agent",
    "run_research_agent",
    "run_verifier_agent",
    "run_writer_agent",
    "run_editor_agent",
    "run_diff_agent",
]
