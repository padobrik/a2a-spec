"""handshake init — scaffold a new agent-handshake project."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agent_handshake.config.loader import DEFAULT_CONFIG_NAMES

console = Console()

CONFIG_TEMPLATE = """# agent-handshake configuration
project_name: "{project_name}"
version: "1.0"

specs_dir: "./handshake/specs"
scenarios_dir: "./handshake/scenarios"

storage:
  backend: local
  path: ./handshake/snapshots

ci:
  replay_mode: exact
"""

# Lines handshake init makes sure .gitignore has.
GITIGNORE_LINES = ["__pycache__/"]

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

  policy:
    - rule: no_internal_ticket_ids
      description: "Internal ticket IDs such as INT-123456 must not reach the customer"
      method: regex
      patterns:
        - '\\bINT-\\d{6}\\b'
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

    a2a_dir = root / "handshake"

    # Create directories
    dirs = [
        a2a_dir / "specs",
        a2a_dir / "snapshots",
        a2a_dir / "scenarios",
        a2a_dir / "adapters",
        a2a_dir / "reports",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  [dim]Created[/dim] {d.relative_to(root)}/")

    # Write config, unless the project has one under any default name: the
    # loader would otherwise pick the new file over the existing one.
    existing = next((n for n in DEFAULT_CONFIG_NAMES if (root / n).exists()), None)
    if existing is None:
        (root / "handshake.yaml").write_text(
            CONFIG_TEMPLATE.format(project_name=project_name),
            encoding="utf-8",
        )
        console.print("  [green]Created[/green] handshake.yaml")
    else:
        console.print(f"  [yellow]Exists[/yellow]  {existing}")

    # Write example spec
    example_spec_path = a2a_dir / "specs" / "example-spec.yaml"
    if not example_spec_path.exists():
        example_spec_path.write_text(EXAMPLE_SPEC, encoding="utf-8")
        console.print("  [green]Created[/green] handshake/specs/example-spec.yaml")

    # Write example scenario
    example_scenario_path = a2a_dir / "scenarios" / "example-scenarios.yaml"
    if not example_scenario_path.exists():
        example_scenario_path.write_text(EXAMPLE_SCENARIO, encoding="utf-8")
        console.print("  [green]Created[/green] handshake/scenarios/example-scenarios.yaml")

    # Write adapters __init__.py
    adapters_init = a2a_dir / "adapters" / "__init__.py"
    if not adapters_init.exists():
        adapters_init.write_text(ADAPTERS_TEMPLATE, encoding="utf-8")

    _update_gitignore(root)

    console.print()
    console.print("[green bold]agent-handshake project initialized.[/green bold]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Add your agents to ADAPTERS in [bold]handshake/adapters/__init__.py[/bold]")
    console.print("  2. Add inputs to [bold]handshake/scenarios/[/bold]")
    console.print("  3. Run [bold]handshake record[/bold] to save snapshots")
    console.print("  4. Run [bold]handshake infer[/bold] or edit [bold]handshake/specs/[/bold]")
    console.print("  5. Run [bold]handshake test[/bold] (or [bold]pytest --handshake[/bold])")


def _update_gitignore(root: Path) -> None:
    """Add the missing GITIGNORE_LINES to .gitignore; never change existing lines."""
    path = root / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    present = {line.strip().rstrip("/") for line in text.splitlines()}
    missing = [line for line in GITIGNORE_LINES if line.rstrip("/") not in present]
    if not missing:
        return
    separator = "\n" if text and not text.endswith("\n") else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(separator + "".join(f"{line}\n" for line in missing))
    action = "Updated" if text else "Created"
    console.print(f"  [green]{action}[/green] .gitignore")
