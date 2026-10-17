"""Planner agent: turns a question into a title and a list of searches. No model."""


async def planner_agent(data: dict) -> dict:
    topic = data["question"].rstrip("?")
    return {
        "title": topic.capitalize(),
        "headers": {"title": f"Report: {topic}"},
        "searches": [
            {"query": f"{topic} overview", "reason": "Background first."},
            {"query": f"{topic} risks", "reason": "What can go wrong."},
        ],
    }
