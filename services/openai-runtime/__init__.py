# openai_runtime — sole module permitted to import the OpenAI SDK.
# All other services call the functions exposed here.
#
# Public interface:
#   run_planner_agent(topic_context)             -> research_plan
#   run_research_agent(research_plan)            -> evidence_set
#   run_verifier_agent(evidence_set)             -> validated_evidence
#   run_writer_agent(validated_evidence, guide)  -> draft_content
#   run_editor_agent(draft_content, instructions)-> final_draft, scorecard
#   run_diff_agent(prior_version, new_draft)     -> diff_summary
