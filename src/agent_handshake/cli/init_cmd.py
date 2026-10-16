"""handshake init — scaffold a new agent-handshake project."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agent_handshake.config.loader import (
    DEFAULT_CONFIG_NAMES,
    LEGACY_CONFIG_NAMES,
    LEGACY_PROJECT_DIR,
    PROJECT_DIR,
)

console = Console()

CONFIG_TEMPLATE = """# agent-handshake configuration
project_name: "{project_name}"
version: "1.0"

specs_dir: "./handshake/specs"
scenarios_dir: "./handshake/scenarios"

semantic:
  provider: sentence-transformers
  model: all-MiniLM-L6-v2
  enabled: true

storage:
  backend: local
  path: ./handshake/snapshots

ci:
  fail_on_semantic_drift: true
  drift_threshold: 0.15
  replay_mode: exact
"""

EXAMPLE_SPEC = """# Example spec — defines what consumer expects from producer
spec:
  name: example-spec
  version: "1.0"
  producer: agent-a
  consumer: agent-b
  description: "Agent B expects this from Agent A"

  structural:
    type: object
    required:
      - category
      - summary
    properties:
      category:
        type: string
        enum: [billing, shipping, product, general]
      summary:
        type: string
        minLength: 10
        maxLength: 500
      confidence:
        type: number
        minimum: 0.0
        maximum: 1.0

  semantic:
    - rule: summary_faithful_to_input
      description: "Summary must reflect the actual input"
      method: embedding_similarity
      threshold: 0.5
      source_field: message
      target_field: summary

  policy:
    - rule: no_pii
      description: "Output must not contain PII"
      method: regex
      patterns:
        - '\\b\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}\\b'  # card number
        - '\\b\\d{3}-\\d{2}-\\d{4}\\b'  # US SSN
"""

ADAPTERS_TEMPLATE = '''"""Agent adapters for agent-handshake.

Map each agent id used in your specs and scenarios to an adapter, for example:

    from agent_handshake import FunctionAdapter
    from agents.triage import triage_agent

    ADAPTERS = {
        "agent-a": FunctionAdapter(fn=triage_agent, agent_id="agent-a", version="1.0"),
    }
"""

from typing import Any

ADAPTERS: dict[str, Any] = {}
'''

EXAMPLE_SCENARIO = """# Example test scenario
test_suite:
  name: example-tests

scenarios:
  - name: basic_test
    input:
      message: "I was charged twice for my order"
    expectations:
      agent-a:
        category: billing
"""


def init_command(
    directory: str = typer.Argument(
        ".", help="Directory to initialize. Defaults to current directory."
    ),
    project_name: str = typer.Option(
        None, "--name", "-n", help="Project name. Defaults to directory name."
    ),
) -> None:
    """Initialize a new agent-handshake project.

    Creates the directory structure, config file, and example specs.
    """
    root = Path(directory).resolve()

    if project_name is None:
        project_name = root.name

    # A new handshake.yaml would take precedence over an a2a-spec project's own
    # config and folder, so the project would silently switch to empty examples.
    legacy = [name for name in LEGACY_CONFIG_NAMES if (root / name).exists()]
    if (root / LEGACY_PROJECT_DIR).is_dir():
        legacy.append(f"{LEGACY_PROJECT_DIR}/")
    if legacy and not any((root / name).exists() for name in DEFAULT_CONFIG_NAMES):
        console.print(
            f"[red]{root} already has an a2a-spec project ({', '.join(legacy)}).[/red]\n"
            "It keeps working with agent-handshake as it is. To move it to the new names, see "
            "https://github.com/padobrik/agent-handshake#rename-from-a2a-spec"
        )
        raise typer.Exit(1)

    project_dir = root / PROJECT_DIR

    # Create directories
    dirs = [
        project_dir / "specs",
        project_dir / "snapshots",
        project_dir / "scenarios",
        project_dir / "adapters",
        project_dir / "reports",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  [dim]Created[/dim] {d.relative_to(root)}/")

    # Write config
    config_path = root / "handshake.yaml"
    if not config_path.exists():
        config_path.write_text(
            CONFIG_TEMPLATE.format(project_name=project_name),
            encoding="utf-8",
        )
        console.print("  [green]Created[/green] handshake.yaml")
    else:
        console.print("  [yellow]Exists[/yellow]  handshake.yaml")

    # Write example spec
    example_spec_path = project_dir / "specs" / "example-spec.yaml"
    if not example_spec_path.exists():
        example_spec_path.write_text(EXAMPLE_SPEC, encoding="utf-8")
        console.print("  [green]Created[/green] handshake/specs/example-spec.yaml")

    # Write example scenario
    example_scenario_path = project_dir / "scenarios" / "example-scenarios.yaml"
    if not example_scenario_path.exists():
        example_scenario_path.write_text(EXAMPLE_SCENARIO, encoding="utf-8")
        console.print("  [green]Created[/green] handshake/scenarios/example-scenarios.yaml")

    # Write adapters __init__.py
    adapters_init = project_dir / "adapters" / "__init__.py"
    if not adapters_init.exists():
        adapters_init.write_text(ADAPTERS_TEMPLATE, encoding="utf-8")

    console.print()
    console.print("[green bold]agent-handshake project initialized.[/green bold]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Add your agents to ADAPTERS in [bold]handshake/adapters/__init__.py[/bold]")
    console.print("  2. Add inputs to [bold]handshake/scenarios/[/bold]")
    console.print("  3. Run [bold]handshake record[/bold] to save snapshots")
    console.print("  4. Run [bold]handshake infer[/bold] or edit [bold]handshake/specs/[/bold]")
    console.print("  5. Run [bold]handshake test[/bold] (or [bold]pytest --handshake[/bold])")
