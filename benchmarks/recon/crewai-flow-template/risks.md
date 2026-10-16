# Silent-breakage risks

- disputed — lib/cli/src/crewai_cli/templates/flow/main.py:25 — `plan_content` reads the external trigger payload with `.get("topic", "AI Agents")`, so a payload without `topic` (for example a renamed key) silently produces and saves a post about "AI Agents".
- disputed — lib/cli/src/crewai_cli/templates/crew/main.py:80-84 — `run_with_trigger` passes `topic` and `current_year` as "", and `interpolate_only` (lib/crewai/src/crewai/utilities/string_utils.py:138-141) fails only on missing keys, so the prompts run with empty values and no error.
- disputed — lib/cli/src/crewai_cli/templates/flow/main.py:13-14 — `ContentState.outline` and `ContentState.draft` default to "" and no step writes them, so a future step that reads them gets "" with no error.
- disputed — lib/crewai/src/crewai/crews/crew_output.py:17 — `CrewOutput.raw` defaults to "", so an empty crew result is saved to `output/post.md` (flow main.py:42, :50) without an error.
