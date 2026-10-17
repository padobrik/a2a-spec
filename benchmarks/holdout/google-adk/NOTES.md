# google-adk: notes

**Example.** `core/python/deep-search` (Deep Search), at commit
05811bbacd9b0335c645e8d20e0d41cfdea08f7f. Picked because it is a core (not
contrib) sample and the repository's main multi-agent pipeline: a root planner,
a SequentialAgent with a LoopAgent, six LLM agents that pass data through
session state (`output_key`), one structured output (`Feedback`), a custom
BaseAgent that reads another agent's output, and two callbacks that read model
output. All code is in `app/agent.py`.

**Links** (L1-L9, one case each):

| link | producer -> consumer | carried by | data form | fields |
|---|---|---|---|---|
| L1 | research_evaluator -> escalation_checker | state `research_evaluation`, `_run_async_impl` | dict from Pydantic `Feedback` | 1 |
| L2 | research_evaluator -> enhanced_search_executor | conversation history, prompt names the key | dict as JSON text | 1 |
| L3 | section_researcher (grounding) -> source_collector | `session.events`, `collect_research_sources_callback` | google.genai typed objects | 11 |
| L4 | enhanced_search_executor (grounding) -> source_collector | same callback | same | 11 |
| L5 | report_composer -> citation_replacement | state `final_cited_report` | text | 0 |
| L6 | interactive_planner_agent -> report_composer | `{research_plan}` placeholder | text | 0 |
| L7 | section_planner -> report_composer | `{report_sections}` placeholder | text | 0 |
| L8 | section_researcher -> report_composer | `{section_research_findings}` placeholder | text | 0 |
| L9 | section_researcher -> research_evaluator | conversation history | text | 0 |

Total: 9 cases, 24 expected fields.

**Data forms.** Shared session state is the channel for everything. Values are
plain strings for five of six agents; the evaluator's state value is the dict of
its Pydantic model. L3/L4 are attribute reads on framework objects (events with
`grounding_metadata`), reached through
`callback_context._invocation_context.session`, not through a parameter.

**Unusual / assumptions.**
- L3/L4: the producer is the model response event, not the agent's
  `output_key` text, so these producers get their own ids
  (`section_researcher_grounding`, `enhanced_search_grounding`) and paths are
  relative to one event. The callback loops over all session events, so it
  would also read grounding from `plan_generator`, which has `google_search`
  too; that link is not listed (the callback is not attached to it).
- L2: `follow_up_queries` is counted although no code substitutes it; the
  instruction tells the model by name to run every query in it (line 344).
  `search_query` and `comment` are not named there, so they are not counted.
- Not listed: `sources` state (written by `collect_research_sources_callback`,
  read by `citation_replacement_callback` at lines 147-159 for `title`,
  `domain`, `url`). It is a callback-to-callback link, not between agents, and
  its keys are dynamic short ids (`src-N`), which the path notation cannot
  express. The composer reads `{sources}` whole.
- Not listed: `research_plan` into `plan_generator` (`{research_plan?}`, line
  205) and the plan named in the section_planner / section_researcher
  instructions; all whole text, 0 fields.
- The React frontend reads `stateDelta.final_report_with_citations` and
  `stateDelta.sources` (frontend/src/App.tsx:163, :180); it is not an agent and
  is not in the cases.
- Pass-grade snapshot uses `follow_up_queries: []` rather than omitting it, so
  it does not depend on how the framework dumps `None`.
