"""Writer agent: builds a short report from the planner's output."""


def writer_agent(plan: dict) -> dict:
    headers = plan.get("headers") or {}
    lines = [f"# {headers.get('title', plan['title'])}"]
    lines += [_search_line(item) for item in plan["searches"]]
    return {"report": "\n".join(lines)}


def _search_line(item: dict) -> str:
    return f"- {item['query']}: {item.get('reason', '')}"
