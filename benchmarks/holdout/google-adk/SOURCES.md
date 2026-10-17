# Sources

All snapshots are written by hand. No agent was run. Shapes come from the agent
definitions in `core/python/deep-search/app/agent.py` (output keys, the
`Feedback` model, the callbacks' reads). The scenario is the example
interaction in `core/python/deep-search/README.md:228-245` (a report on the last
Google I/O). Report and findings texts are short placeholders. Paths are
relative to the repository root; `agent.py` below is
`core/python/deep-search/app/agent.py`.

| file | repository@short-sha | where the shape and values come from (file:line) |
|---|---|---|
| handshake/snapshots/interactive_planner_agent/google_io_001.json | google/adk-recipes@05811bb | Free text: `output_key="research_plan"` on an LlmAgent without output schema, agent.py:403-424. Bullets from core/python/deep-search/README.md:232-236; the `[RESEARCH]` / `[DELIVERABLE][IMPLIED]` prefixes from the plan_generator instruction, agent.py:207-216. |
| handshake/snapshots/section_planner/google_io_001.json | google/adk-recipes@05811bb | Free text: markdown outline of 4-6 `# Section` headings, `output_key="report_sections"`, agent.py:240-251. Section texts are placeholders. |
| handshake/snapshots/section_researcher/google_io_001.json | google/adk-recipes@05811bb | Free text: research summaries plus deliverables, `output_key="section_research_findings"`, agent.py:262-301 (final output format at :298). Texts are placeholders. |
| handshake/snapshots/research_evaluator/google_io_fail_001.json | google/adk-recipes@05811bb | Dict from the `Feedback` model, agent.py:36-56 (`grade` Literal "pass"/"fail", `comment`, `follow_up_queries: list[SearchQuery]` with `search_query`); `output_schema=Feedback`, `output_key="research_evaluation"` at :326-329. Five queries per the "5-7 follow-up queries" rule at :319-320. Query texts are placeholders. |
| handshake/snapshots/research_evaluator/google_io_pass_001.json | google/adk-recipes@05811bb | Same model, agent.py:36-56, grade "pass"; `follow_up_queries` is empty as the field description at :55 asks ("null or empty if the grade is 'pass'"). |
| handshake/snapshots/report_composer/google_io_001.json | google/adk-recipes@05811bb | Free text with `<cite source="src-N" />` tags, `output_key="final_cited_report"`, agent.py:358-380 (tag format at :372, regex at :162). Input keys are the four placeholders at :363-366; the `sources` record shape is the one built at :97-103. Texts are placeholders. |
| handshake/snapshots/section_researcher_grounding/google_io_001.json | google/adk-recipes@05811bb | One model response event of section_researcher (`author` from the agent name, agent.py:257). `grounding_metadata` shape from the reads in `collect_research_sources_callback`, agent.py:78-126: `grounding_chunks[].web.{uri,title,domain}`, `grounding_supports[].{segment.text, grounding_chunk_indices, confidence_scores}`; `segment.start_index`/`end_index` and `web_search_queries` are other fields of the google.genai grounding types, not read. The second chunk has title equal to domain, the case handled at :89-92. URLs and texts are placeholders. |
| handshake/snapshots/enhanced_search_grounding/google_io_001.json | google/adk-recipes@05811bb | Same event shape for enhanced_search_executor (agent.py:332-351, same callback at :350). Input is the evaluator feedback it is told to review, :343-344. |
