# Notes

Assumptions made where the request or the code was ambiguous.

## Semantic rules in `handshake test`

- `embedding_similarity` compares `input[source_field]` from the snapshot with
  `output[target_field]`. Both fields are required; a rule without them fails
  rather than guessing which text to compare. Fields are top-level keys only.
- `entailment` and `language_detection` are declared in the schema but were
  never implemented. They now fail with "not implemented" instead of passing
  silently.
- Without the `semantic` extra the command exits 1 with an install hint.
  Skipping is opt-in (`--no-semantic` or `semantic.enabled: false`) and the
  report shows `semantic SKIPPED`, so a missing dependency never turns into a
  silent pass.
- The example spec threshold moved from 0.8 to 0.5. 0.8 had never been
  executed; with `all-MiniLM-L6-v2` the example's own faithful summary scores
  0.78, other faithful summaries 0.61–0.81, off-topic ones 0.28–0.31.

## Dependency bumps

- The pending dependabot PRs were reproduced on a branch instead of being
  merged on GitHub; the remote was not reachable from this environment.

## `handshake infer`

- The consumer is analyzed statically (no import, no execution). The first
  parameter after `self`/`cls` is taken to be the producer's output.
- Literal string keys are tracked through nested reads (`data["a"]["b"]`,
  `data.get("a", {}).get("b")`, `"b" in data["a"]`) and through a local name
  bound to a nested value (`a = data["a"]`). The binding is followed in
  source order and dropped when the name is assigned something else; branches
  and loops are not analyzed.
- Using such a local name as a whole (`helper(a)`) warns only when the code
  also reads keys from it: otherwise it most likely holds a leaf value such
  as a string. For the same reason, method calls and integer indexes on a
  nested value (`data["tier"].lower()`, `data["tags"][0]`) do not warn;
  mapping methods (`.items()`, `.keys()`, ...) do.
- A nested field is required when the consumer reads it with `[]`, or when
  it is present in every snapshot that contains its parent. Its parent's own
  required status is decided separately at its level.
- List items (`data["items"][0]["sku"]`) are not followed; only `items` is
  recorded.
- A field read via `.get()` or `in` is required when every snapshot contains
  it, because a silent fallback is the failure the tool exists to catch.
- `enum` constraints are not inferred: snapshots show which values were
  sent, not which values are allowed.
- TypeScript and JavaScript consumers are parsed with tree-sitter (the
  `typescript` extra) instead of the TypeScript compiler, so Node.js is not
  needed and types are not resolved. `.js`, `.jsx` and `.tsx` use the TSX
  grammar, which also parses plain JavaScript.
- In JavaScript a missing key gives `undefined`, so the last key of a read is
  never strict. An earlier key is strict when the code reads through it
  without `?.` or a destructuring default, or calls a method on it, because
  that throws at run time.
- `.length` and method calls on a read value (`data.tags.length`,
  `data.category.toLowerCase()`) are treated as uses of a string or array, not
  as fields of the input.

## pytest plugin

- The plugin is installed with the package but stays inert unless enabled
  (`--handshake`, `--handshake-config`, or `handshake_config` in the ini file), so installing
  agent-handshake never changes an unrelated test suite.
- Relative paths resolve like the CLI (working directory); a path set in the
  ini file resolves relative to that ini file.
- A spec whose producer has no snapshots is reported as a skip, matching the
  CLI's warning rather than failing.

## `handshake diff`

- The baseline is the committed version of each snapshot file (`--base`,
  default `HEAD`), matching the README's "commit snapshots to git — they
  become your test baselines". The previous behaviour (compare the last two
  files of a scenario, ordered by hash) could not see re-recorded changes.
  Outside a git repository diff now exits 1 with an explanation.
- A deleted snapshot counts as high severity so it cannot slip through CI.

## Agent skill

- The skill lives in the package (`agent_handshake/skill/SKILL.md`) so its commands
  always match the installed CLI; `handshake skill --dir` takes the skills
  directory explicitly instead of guessing a tool-specific default.

## A2A adapter

- Supports A2A 1.0 over JSON-RPC only (the protocol version current in
  a2a-sdk 1.2.2). 0.3 agents are rejected with an explicit message rather
  than half-supported; gRPC and HTTP+JSON are out of scope.
- Streaming is opt-in (`streaming=True`) and needs `capabilities.streaming`
  in the card, so an agent is never sent a method it did not declare.
  Events are folded the way a2a-sdk folds them: a new artifact with an
  existing id replaces it, `append` extends its parts (text chunks stay
  separate parts and are joined with newlines like any other text parts),
  and `append` to an unknown artifact is an error. The result is checked
  only after the stream ends, so the snapshot does not depend on streaming.
- Input goes out as one `data` part by default because contracts are about
  structured fields; `text_field` covers text-only agents.
- `json_text` is opt-in so the adapter never reinterprets an agent's text
  reply unless asked.
- File parts go under `"files"`. Raw bytes are replaced by `size` and
  `sha256`: a contract checks the shape of the reply, and base64 content
  would make snapshots large and diffs unreadable. Parts with no known
  content key raise instead of being dropped.
- `agent_id` is required: it must match the producer/consumer ids in specs,
  which the agent's card name does not guarantee.

## Rename to agent-handshake

- No compatibility layer for the old a2a-spec names (command, config file,
  project folder, pytest options, class names, PyPI package): the owner
  confirmed the project had no users at the time of the rename.
- `a2a-spec` stays on PyPI at 0.6.0 as it is; no further releases.

## LLM example

- `examples/llm_support` calls a hosted model through its vendor's SDK and
  names that vendor in its code and README. The owner approved this as an
  exception for the example only; commit messages and PR descriptions stay
  free of vendor and assistant names.
- Snapshots are not committed until they are recorded with a real API key,
  so the example never shows made-up model output as recorded output.
