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
