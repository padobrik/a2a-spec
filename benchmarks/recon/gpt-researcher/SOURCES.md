# Sources

All snapshots are written by hand from the code at assafelovic/gpt-researcher@3582a68. Each output copies the
producer's `return` statement. Values made by an LLM follow the JSON shape the
prompt asks for. `task` is `multi_agents/task.json` in every snapshot. Paths are relative to the repository root.
Specs were generated with `handshake infer` from these snapshots; `--allow-missing`
was passed for fields that another producer (or the user task) writes into the shared
LangGraph state.

| file | source | where the shape and values come from |
|---|---|---|
| handshake/snapshots/browser/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/researcher.py:50` returns `task` and `initial_research` (markdown report string); `task` is `multi_agents/task.json` |
| handshake/snapshots/planner/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/editor.py:51-55` returns `title`, `date`, `sections`; shape from the prompt at `editor.py:118-121`; 3 sections because `max_sections: 3` in `task.json` |
| handshake/snapshots/human/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/human.py:58-61`; `include_human_feedback: false` in `task.json`, so `human_feedback` is null and the counter stays 0 (`human.py:16,52-54`) |
| handshake/snapshots/human/feedback_given_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/human.py:43-61` with `include_human_feedback: true`: free-text feedback, counter incremented at `human.py:53-54` |
| handshake/snapshots/editor/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/editor.py:184-192` (`_create_task_input`): `task`, `topic`, `title`, `headers` (`{}` by default, `editor.py:25`), `sibling_sections` |
| handshake/snapshots/depth_researcher/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/researcher.py:66` returns `{"draft": {subtopic: report}}` (`researcher.py:39`) |
| handshake/snapshots/reviewer/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/reviewer.py:84`; `follow_guidelines: false` in `task.json`, so `review` is null (`reviewer.py:72-83`) |
| handshake/snapshots/reviewer/needs_revision_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/reviewer.py:84-86` with `follow_guidelines: true`: review notes (text) and `draft_revision_count` 1 |
| handshake/snapshots/researcher/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/editor.py:78-82` returns `research_data`, a list of `{section: report}` dicts (`researcher.py:39`) |
| handshake/snapshots/writer/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/writer.py:146`: LLM JSON keys from `writer.py:6-13` plus `headers` from `writer.py:22-30` |
| handshake/snapshots/fact_checker/hype_cycle_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/fact_checker.py:49-50,61`: accepted draft, `fact_check_notes` null |
| handshake/snapshots/fact_checker/issues_found_1.json | assafelovic/gpt-researcher@3582a68 | `multi_agents/agents/fact_checker.py:61-65`: notes text and `fact_check_revision_count` 1 |
| handshake/specs/browser-to-planner.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/editor.py:plan_research`, `--allow-missing human_feedback` |
| handshake/specs/planner-to-human.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/human.py:review_plan`, `--allow-missing task --allow-missing plan_revision_count` |
| handshake/specs/human-to-plan_router.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/plan_review.py:route_human_feedback` |
| handshake/specs/planner-to-researcher.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/editor.py:run_parallel_research` (WARN line 75) |
| handshake/specs/editor-to-depth_researcher.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/researcher.py:run_depth_research`, `--allow-missing task.source` (not in `task.json`) |
| handshake/specs/depth_researcher-to-reviewer.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/reviewer.py:run`, `--allow-missing task --allow-missing draft_revision_count` (WARN line 81) |
| handshake/specs/reviewer-to-editor_draft_router.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/editor.py:_route_draft_review`, `--allow-missing task` (WARN line 162) |
| handshake/specs/reviewer-to-draft_router.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/draft_review.py:route_draft_review` |
| handshake/specs/reviewer-to-reviser.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/reviser.py:run`, `--allow-missing task` (WARN line 56) |
| handshake/specs/researcher-to-writer.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/writer.py:run`, `--allow-missing task` (WARN lines 112, 128) |
| handshake/specs/writer-to-fact_checker.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/fact_checker.py:run`, `--allow-missing fact_check_revision_count` (WARN line 45) |
| handshake/specs/fact_checker-to-fact_router.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/fact_review.py:route_fact_check` |
| handshake/specs/writer-to-publisher.yaml | assafelovic/gpt-researcher@3582a68 | `handshake infer` on `multi_agents/agents/publisher.py:run`, `--allow-missing task` (WARN line 88) |
