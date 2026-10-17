# mastra holdout notes

## Example

`templates/template-github-review-agent/src/mastra/workflows/pr-review-workflow.ts`, the
`pr-review-workflow` that the template's README presents as its fixed 4-step pipeline
(README.md:57). Picked because it is a shipped template, chains four `createStep` steps
with Zod input and output schemas, each step reading the previous step's output from
`inputData`, and two of the steps call a model (`workflow-review-agent`). It also has
helper functions (`buildFileSection`, a nested `buildPrompt`), destructuring, list items
and nested objects, so the reads are not all on the first line of the consumer.

## Links

| link | producer step | consumer step | consumer source | data form | expected fields |
|---|---|---|---|---|---|
| L1 | fetch_pr_context | categorize_files | `categorizeFiles` execute | typed object (Zod `prContextSchema`) | 8 |
| L2 | categorize_files | review_files | `reviewFiles` execute, helper `buildFileSection` | typed object (Zod `categorizedSchema`) | 20 |
| L3 | review_files (agent structured output) | aggregate_findings | `aggregateFindings` execute | typed object (Zod `reviewedSchema`) | 15 |

Total: 3 cases, 43 expected fields.

## Data forms

All three links pass a plain object validated by Zod schemas, handed to the next step's
`execute({ inputData })`. No shared workflow state and no free text between steps. Inside
the steps, the agent output is read through `response.object`.

## Assumptions and unusual points

- `source` names the step constant (`categorizeFiles`, `reviewFiles`, `aggregateFindings`),
  because the receiving function is an anonymous `execute` arrow inside `createStep({...})`.
- Destructuring a key from `inputData` counts as reading that field, even when the value is
  only passed on whole (`pr` in L1, `owner`/`repo`/`pullNumber` in L1 and L2, `skippedFiles`).
- In L2 the reviewable files are copied with `{ ...file, content }` and the copies are
  read in `buildFileSection` (via `batchFiles`). Those reads count as fields of
  `reviewableFiles[]`, because they are the producer's fields. `content` is added by the
  consumer, so it is not a field. `.length` is not counted as a field.
- The two agent calls inside steps (the review agent's per-file findings and the aggregate
  summary) are not separate cases: the step code uses `response.object` whole (spread or
  `?? []`), so they would have no fields. The per-file findings are covered as
  `fileReviews` in L3.
- `aggregateFindings` does not read `owner`, `repo` or `pullNumber`; they are dropped.
