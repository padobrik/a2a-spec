# Sources

All files are written by hand from the code at crewAIInc/crewAI@cf9f08a. Paths are relative to the repository root. `F` = `lib/cli/src/crewai_cli/templates/flow`, `C` = `lib/cli/src/crewai_cli/templates/crew`, `K` = `lib/crewai/src/crewai`. Free text that a model writes (`raw` values) is a short stand-in string; any string is possible there.

| file | repository@short-sha | where the shape and values come from |
|---|---|---|
| handshake/snapshots/trigger/with_topic_001.json | crewAIInc/crewAI@cf9f08a | key `topic` from F/main.py:25; value is the code's own default "AI Agents" (F/main.py:25, :28); payload parsed at F/main.py:75 |
| handshake/snapshots/plan_content/default_topic_001.json | crewAIInc/crewAI@cf9f08a | `ContentState` fields and defaults F/main.py:11-15; `topic` set at F/main.py:28 |
| handshake/snapshots/content_crew/ai_agents_001.json | crewAIInc/crewAI@cf9f08a | `CrewOutput` fields K/crews/crew_output.py:17-26; input from F/main.py:38; `raw` is a stand-in for the editor's markdown post (F/crews/content_crew/config/tasks.yaml:46-48) |
| handshake/snapshots/generate_content/ai_agents_001.json | crewAIInc/crewAI@cf9f08a | `ContentState` after F/main.py:42 (`final_post = result.raw`); same stand-in text as above |
| handshake/snapshots/planner/ai_agents_001.json | crewAIInc/crewAI@cf9f08a | `TaskOutput` fields K/tasks/task_output.py:30-44; `description` and `expected_output` from F/crews/content_crew/config/tasks.yaml:3, :13-15; `agent` from F/crews/content_crew/config/agents.yaml:2-3; `raw` is a stand-in outline |
| handshake/snapshots/generate_content_inputs/ai_agents_001.json | crewAIInc/crewAI@cf9f08a | kickoff inputs dict F/main.py:38 with the default topic |
| handshake/snapshots/crew_run_inputs/run_001.json | crewAIInc/crewAI@cf9f08a | inputs dict C/main.py:16-19 (`current_year` is `str(datetime.now().year)`) |
| handshake/snapshots/crew_run_inputs/trigger_001.json | crewAIInc/crewAI@cf9f08a | inputs dict C/main.py:80-84 (`topic` and `current_year` are ""); payload content is up to the caller |
| handshake/specs/trigger-to-plan_content.yaml | crewAIInc/crewAI@cf9f08a | `handshake infer` on F/main.py:plan_content (rendered with `{{folder_name}}` -> `my_flow`) and the trigger snapshot |
| handshake/specs/generate_content_inputs-to-planning_task.yaml | crewAIInc/crewAI@cf9f08a | `handshake infer --allow-missing crew_chat_messages` on the framework function K/task.py:interpolate_inputs_and_add_conversation_history (closest function; the template has none); the one field is framework-only (K/task.py:1117, :1122) |
| handshake/specs/crew_run_inputs-to-research_task.yaml | crewAIInc/crewAI@cf9f08a | same as above, with the two crew_run_inputs snapshots |
