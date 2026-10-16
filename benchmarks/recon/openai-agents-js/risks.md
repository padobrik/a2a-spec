# Silent-breakage risks

- disputed — examples/financial-research-agent/manager.ts:26 — `summaryExtractor` types its input as `any` and returns `String(runResult.finalOutput.summary)`, so if the fundamentals or risk agent stops sending `summary` the writer gets the text "undefined" with no error (latent: both agents use `AnalysisSummary` today, agents.ts:18, 64).
- disputed — examples/financial-research-agent/manager.ts:119 — `search` returns `String(result.finalOutput)`, so an undefined final output becomes the text "undefined", passes the blank filter at manager.ts:48-50 and reaches the writer prompt (framework internals: needs a run that ends without a final output).
