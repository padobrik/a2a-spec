# Notes

Assumptions made where the request or the code was ambiguous.

## Semantic rules in `a2aspec test`

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

## `a2aspec infer`

- The consumer is analyzed statically (no import, no execution). The first
  parameter after `self`/`cls` is taken to be the producer's output.
- Only top-level string keys are tracked; nested reads (`data["a"]["b"]`)
  contribute only the top-level field `a`.
- A field read via `.get()` or `in` is required when every snapshot contains
  it, because a silent fallback is the failure the tool exists to catch.
- `enum` constraints are not inferred: snapshots show which values were
  sent, not which values are allowed.

## pytest plugin

- The plugin is installed with the package but stays inert unless enabled
  (`--a2a`, `--a2a-config`, or `a2a_config` in the ini file), so installing
  a2a-spec never changes an unrelated test suite.
- Relative paths resolve like the CLI (working directory); a path set in the
  ini file resolves relative to that ini file.
- A spec whose producer has no snapshots is reported as a skip, matching the
  CLI's warning rather than failing.
