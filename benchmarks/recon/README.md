# Recon benchmark

Five open-source multi-agent projects from the phase 3 recon (see
`docs/recon/`), frozen at one commit each. For every consumer function the
benchmark lists the fields it really reads from the producer's output. It
measures how many of them `handshake infer` finds.

```bash
make benchmark                 # or: python scripts/benchmark.py
python scripts/benchmark.py --project gpt-researcher -v   # per case: missed and false fields
```

The script fetches each repository at its commit into `.cache/benchmarks/`
(network needed once), runs the consumer analysis on each case and prints:

- **found**: expected fields the analysis reports;
- **total**: expected fields;
- **false**: fields the analysis reports that are not expected (a spec would
  contain a field the consumer does not read from the producer).

## Files per project

- `benchmark.yaml`: repository, full commit, and the cases. A case names the
  consumer function (`source: path:function`, or `null` when no function
  receives the data, such as prompt templates) and its expected fields, each
  with the file:line where it is read. `replace` renders template files that
  do not parse as they are.
- `handshake/`: the snapshots and specs written during the recon run.
- `SOURCES.md`: where the shape and values of each snapshot and spec come from.
- `risks.md`: the silent-breakage risks found, marked explicit (an agent reads
  another agent's output with a default the producer does not guarantee) or
  disputed (external input, framework internals, or latent).

## Counting rules

- Paths are relative to the producer's output: `customer.tier`. Parents are
  listed as fields too, as in a spec. `searches[].query` is a field of each
  item of the list `searches`. A found parent of an expected field (`a` for
  `a.b`) is never false, even when the list does not name it.
- A field counts once per case, wherever the consumer reads it: a key, `.get`,
  `in`, an attribute, `getattr(obj, "field", default)`, or a helper function
  that receives the data.
- Whole-object uses (`model_dump`, `JSON.stringify`, `str(obj)`) are not fields.
- A read through a framework wrapper (`run_result.final_output.summary`) is the
  field `summary`.

All snapshots were written by hand from each project's code, tests and sample
outputs. No project code was run.
