"""Build and validate agent pipeline DAGs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from a2a_spec.exceptions import ConfigError


@dataclass
class Edge:
    """A directed edge in the pipeline DAG."""

    from_agent: str
    to_agent: str
    condition: str | None = None  # Expression evaluated against output


@dataclass
class PipelineDAG:
    """Directed acyclic graph of agents.

    Represents the flow of data through a multi-agent pipeline,
    including conditional routing and fan-in/fan-out.
    """

    name: str
    agents: list[str]
    edges: list[Edge]

    def entry_agents(self) -> list[str]:
        """Agents with no incoming edges (pipeline entry points)."""
        targets = {e.to_agent for e in self.edges}
        return [a for a in self.agents if a not in targets]

    def exit_agents(self) -> list[str]:
        """Agents with no outgoing edges (pipeline endpoints)."""
        sources = {e.from_agent for e in self.edges}
        return [a for a in self.agents if a not in sources]

    def successors(self, agent_id: str) -> list[Edge]:
        """Get outgoing edges from an agent."""
        return [e for e in self.edges if e.from_agent == agent_id]

    def predecessors(self, agent_id: str) -> list[Edge]:
        """Get incoming edges to an agent."""
        return [e for e in self.edges if e.to_agent == agent_id]

    def topological_order(self) -> list[str]:
        """Return agents in topological order.

        Raises:
            ConfigError: If the graph contains a cycle.
        """
        agent_set = set(self.agents)
        in_degree: dict[str, int] = {a: 0 for a in self.agents}
        for edge in self.edges:
            if edge.to_agent in agent_set and edge.from_agent in agent_set:
                in_degree[edge.to_agent] += 1

        queue = [a for a in self.agents if in_degree[a] == 0]
        order: list[str] = []

        while queue:
            agent = queue.pop(0)
            order.append(agent)
            for edge in self.successors(agent):
                if edge.to_agent not in in_degree:
                    continue
                in_degree[edge.to_agent] -= 1
                if in_degree[edge.to_agent] == 0:
                    queue.append(edge.to_agent)

        if len(order) != len(self.agents):
            raise ConfigError(
                f"Pipeline '{self.name}' contains a cycle. "
                f"Processed {len(order)}/{len(self.agents)} agents."
            )

        return order

    def validate(self) -> list[str]:
        """Validate the DAG structure. Returns list of errors."""
        errors: list[str] = []

        # Check for unknown agents in edges
        agent_set = set(self.agents)
        for edge in self.edges:
            if edge.from_agent not in agent_set:
                errors.append(f"Edge references unknown agent: '{edge.from_agent}'")
            if edge.to_agent not in agent_set:
                errors.append(f"Edge references unknown agent: '{edge.to_agent}'")

        # Check for cycles
        try:
            self.topological_order()
        except ConfigError as e:
            errors.append(str(e))

        # Check for unreachable agents
        entry = set(self.entry_agents())
        reachable: set[str] = set(entry)
        frontier = list(entry)
        while frontier:
            current = frontier.pop()
            for edge in self.successors(current):
                if edge.to_agent not in reachable:
                    reachable.add(edge.to_agent)
                    frontier.append(edge.to_agent)

        unreachable = agent_set - reachable
        if unreachable:
            errors.append(f"Unreachable agents: {sorted(unreachable)}")

        return errors


def build_dag(pipeline_spec: dict[str, Any]) -> PipelineDAG:
    """Build a PipelineDAG from a parsed YAML spec.

    Args:
        pipeline_spec: The 'pipeline' section of a pipeline YAML file.

    Returns:
        A validated PipelineDAG.

    Raises:
        ConfigError: If the pipeline spec is invalid.
    """
    agents = list(pipeline_spec.get("agents", {}).keys())

    edges: list[Edge] = []
    for edge_spec in pipeline_spec.get("edges", []):
        from_agents = edge_spec["from"]
        to_agents = edge_spec["to"]

        if isinstance(from_agents, str):
            from_agents = [from_agents]
        if isinstance(to_agents, str):
            to_agents = [to_agents]

        for fa in from_agents:
            for ta in to_agents:
                edges.append(
                    Edge(
                        from_agent=fa,
                        to_agent=ta,
                        condition=edge_spec.get("condition"),
                    )
                )

    dag = PipelineDAG(
        name=pipeline_spec.get("name", "unnamed"),
        agents=agents,
        edges=edges,
    )

    errors = dag.validate()
    if errors:
        raise ConfigError(
            f"Invalid pipeline '{dag.name}':\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return dag
