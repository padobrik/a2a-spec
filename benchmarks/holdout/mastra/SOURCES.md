# Sources

All snapshots are written by hand. No project code was run. The shapes come from the Zod
schemas the steps declare. The text values (PR title, file names, diffs, review messages)
are short placeholders in the style of the review agent's prompt. Paths are relative to
the repository root; W = templates/template-github-review-agent/src/mastra.

| file | repository@short-sha | where the shape and values come from (file:line) |
|---|---|---|
| handshake/snapshots/fetch_pr_context/timezone_fix_001.json | mastra-ai/mastra@0e1d0dc | Input: `prIdentifierSchema` in W/lib/schemas.ts:7-11. Output: `prContextSchema` in W/workflows/pr-review-workflow.ts:19-26 (owner, repo, pullNumber, pr, files), built at :47-53. `pr` is `prSchema` (W/lib/schemas.ts:13-27) as mapped by `mapPRResponse` (W/lib/github.ts:25-41). Each file is `fileSchema` (W/lib/schemas.ts:29-36) as mapped by `mapFilesResponse` (W/lib/github.ts:43-52); `patch` is left out for the lockfile, since it is optional (:50). |
| handshake/snapshots/categorize_files/timezone_fix_001.json | mastra-ai/mastra@0e1d0dc | Input: the fetch_pr_context output above. Output: `categorizedSchema` in W/workflows/pr-review-workflow.ts:27-30, built at :77. pnpm-lock.yaml goes to skippedFiles because it matches `/pnpm-lock\.yaml$/` in W/lib/review-config.ts:10 (checked at pr-review-workflow.ts:67-68). |
| handshake/snapshots/review_files/timezone_fix_001.json | mastra-ai/mastra@0e1d0dc | Input: the categorize_files output above. Output: `reviewedSchema` in W/workflows/pr-review-workflow.ts:31-34, built at :177-184. `fileReviews` items are `fileReviewSchema` (W/lib/schemas.ts:38-48), the structured output asked of the agent at pr-review-workflow.ts:159-161; severity and category values are from the enums at schemas.ts:42-43. One issue has no `line`, which is optional (:44). |
| handshake/snapshots/review_files/docs_only_001.json | mastra-ai/mastra@0e1d0dc | Same shape as above, for a one-file PR with no issues (the prompt at W/workflows/pr-review-workflow.ts:155 asks for an empty issues array when nothing is found). `pr.body` is null, as `prSchema` allows (W/lib/schemas.ts:15) and the prompt handles at pr-review-workflow.ts:145 and :214. `skippedFiles` is empty. |
