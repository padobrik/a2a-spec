"""a2aspec init — scaffold a new a2a-spec project."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()

CONFIG_TEMPLATE = """# a2a-spec configuration
project_name: "{project_name}"
version: "1.0"

specs_dir: "./a2a_spec/specs"
scenarios_dir: "./a2a_spec/scenarios"

semantic:
  provider: sentence-transformers
  model: all-MiniLM-L6-v2
  enabled: true

storage:
  backend: local
  path: ./a2a_spec/snapshots

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
      threshold: 0.8

  policy:
    - rule: no_pii
      description: "Output must not contain PII"
      method: regex
      patterns:
        - '\\\\b\\\\d{4}[- ]?\\\\d{4}[- ]?\\\\d{4}[- ]?\\\\d{4}\\\\b'
        - '\\\\b\\\\d{3}-\\\\d{2}-\\\\d{4}\\\\b'
"""

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
    """Initialize a new a2a-spec project.

    Creates the directory structure, config file, and example specs.
    """
    root = Path(directory).resolve()

    if project_name is None:
        project_name = root.name

    a2a_dir = root / "a2a_spec"

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

    # Write config
    config_path = root / "a2a-spec.yaml"
    if not config_path.exists():
        config_path.write_text(
            CONFIG_TEMPLATE.format(project_name=project_name),
            encoding="utf-8",
        )
        console.print("  [green]Created[/green] a2a-spec.yaml")
    else:
        console.print("  [yellow]Exists[/yellow]  a2a-spec.yaml")

    # Write example spec
    example_spec_path = a2a_dir / "specs" / "example-spec.yaml"
    if not example_spec_path.exists():
        example_spec_path.write_text(EXAMPLE_SPEC, encoding="utf-8")
        console.print("  [green]Created[/green] a2a_spec/specs/example-spec.yaml")

    # Write example scenario
    example_scenario_path = a2a_dir / "scenarios" / "example-scenarios.yaml"
    if not example_scenario_path.exists():
        example_scenario_path.write_text(EXAMPLE_SCENARIO, encoding="utf-8")
        console.print("  [green]Created[/green] a2a_spec/scenarios/example-scenarios.yaml")

    # Write adapters __init__.py
    adapters_init = a2a_dir / "adapters" / "__init__.py"
    if not adapters_init.exists():
        adapters_init.write_text(
            '"""Agent adapters for a2a-spec."""\n',
            encoding="utf-8",
        )

    console.print()
    console.print("[green bold]a2a-spec project initialized.[/green bold]")
    console.print()
    console.print("Next steps:")
    console.print("  1. Edit [bold]a2a_spec/specs/[/bold] to define your agent specs")
    console.print("  2. Create adapters in [bold]a2a_spec/adapters/[/bold]")
    console.print("  3. Run [bold]a2aspec record[/bold] to capture baselines")
    console.print("  4. Run [bold]a2aspec test --replay[/bold] in CI")
