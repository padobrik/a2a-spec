# ai-scientist-v2: notes

**Example.** The main pipeline, `launch_scientist_bfts.py`, after the ideation script
`ai_scientist/perform_ideation_temp_free.py`. The README describes this as the way to
use the project: generate ideas, then pass the idea JSON to the launcher, which runs
experiments (tree search), plot aggregation, citations, the ICBINB writeup (default
`--writeup-type icbinb`) and the review. Picked because it is the shipped main chain
and ships sample ideation outputs (`ai_scientist/ideas/*.json`).

**Links.**

| link | producer -> consumer | consumer function | data form | fields |
|---|---|---|---|---|
| L1 | ideation -> launcher | none (module `__main__`) | model JSON -> dict (list of ideas in a file) | 1 |
| L2 | ideation -> launcher | `bfts_utils.py:idea_to_markdown` | dict, iterated whole | 0 |
| L3 | ideation -> experiments | `agent_manager.py:__init__` | idea.json text -> `json.loads` -> `self.task_desc` | 6 |
| L4 | experiments -> writeup | `perform_icbinb_writeup.py:filter_experiment_summaries` | JSON file -> dict, key whitelist | 10 |
| L5 | figure_review -> writeup | `perform_icbinb_writeup.py:perform_writeup` | model JSON -> dict, local variable | 1 |
| L6 | capref_review -> writeup | `perform_icbinb_writeup.py:perform_writeup` | dict of model JSON, whole into prompt | 0 |
| L7 | writeup -> review | `perform_llm_review.py:perform_review` | PDF -> text | 0 |

7 cases, 18 expected fields.

**Data forms.** No framework and no typed models. Stages pass plain dicts, mostly
model JSON pulled out of a fenced block (`extract_json_between_markers`), and hand them
on through files on disk (`ideas.json`, `idea.json`, `logs/0-run/*_summary.json`, the
PDF), not through function returns. The review output is only dumped to a file by the
launcher, so it has no consumer case.

**Unusual points and assumptions.**
- L1 reads happen in the module-level `__main__` block, so `source` is null.
- L3: the idea crosses as a JSON string (`load_task_desc` returns the file text) and is
  parsed inside the consumer; the reads sit in other methods via `self.task_desc`.
  The five required keys are also checked by a literal list at
  `agent_manager.py:126-134`. `Code` is added by the launcher, not the ideation model
  (`launch_scientist_bfts.py:242`); it is counted because the consumer reads it from the
  same dict. `Experiments` is indexed (`[0]`) and its dict items are iterated whole, so
  no item fields are counted.
- L4: the consumer selects keys by membership in literal sets while iterating
  `.keys()`, then copies them and dumps them whole into a prompt. The selection is
  counted as reads of the named keys, for all three step variants of the function. The
  `BASELINE_SUMMARY` / `RESEARCH_SUMMARY` wrapper added by `load_exp_summaries` is not
  part of the producer output and is dropped from the paths. The ablation summary (a
  top-level list, `ablation_name` read at line 736) is a different file shape and is
  left out to keep one producer shape.
- The legacy 8-page writeup (`perform_writeup.py`, `--writeup-type normal`) has the same
  `Img_description` read at line 605; only the default ICBINB writeup is cased.
- The review ensemble / meta-review path in `perform_review` is not used by the launcher
  (`num_reviews_ensemble=1`), so it is not cased.
