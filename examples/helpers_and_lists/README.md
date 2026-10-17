# Helpers and lists example

The consumer reads part of the producer's output in a helper function, and
reads each item of a list. `handshake infer` follows both.

- **Planner agent** (`agents/planner.py`) returns a dict with `title`,
  `headers.title` and a list `searches`, where each item has `query` and
  `reason`. Plain Python, no model.
- **Writer agent** (`agents/writer.py`) takes the title from
  `plan.get("headers") or {}`, falls back to `plan["title"]`, and gives each
  search to the helper `_search_line`, which reads `item["query"]` and
  `item.get("reason", "")`.

## Run it

Run every command from `examples/helpers_and_lists`.

```bash
handshake record
handshake infer --producer planner-agent --consumer writer-agent \
  --source agents/writer.py:writer_agent
handshake test
handshake infer --check
```

The spec in `handshake/specs/planner-agent-to-writer-agent.yaml` names:

- `headers` and `headers.title`, through the `or {}` fallback (lines 5, 6);
- `title` (line 6);
- `searches`, an array, and the fields of its items, `searches[].query` and
  `searches[].reason`, which are read in `_search_line` (line 12).

For the list, the spec has `type: array` with an `items` schema, so every item
is checked. If the planner drops `query` from one search, `handshake test`
fails that scenario with `'query' is a required property`.

`infer` follows helper functions in the same file, up to three levels, and
methods called through `self.`. A function in another file is not followed:
`infer` then prints a `WARN` line and sets `reads_unknown_keys: true`.
