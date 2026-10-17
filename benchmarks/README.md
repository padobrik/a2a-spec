# Benchmarks

Every rule is measured here before it is turned on. `make benchmark` will print,
for each rule, recall on the dev cases, recall on the holdout cases and
precision on the corpus. No network is used.

## Recall cases (`cases/`)

`cases/index.tsv` lists the 39 known cases of prompt and tool drift and their
sources (commit or issue). Its columns:

- `kind`: what drifted (`tool_name`, `naming`, `args`, `enum`, `keys`,
  `unavailable`, `orphan`, `code_ref`, `semantic`, `dispatch`);
- `detect`: how it could be caught. `E` a name not in the tools, `N` a near
  match, `A` arguments, `V` values or keys, `O` a tool never mentioned, `C` code
  or configuration that names a tool, `S` meaning only, `X` not caught this way;
- `visibility`: `static` when the prompt and tools are in the source,
  `runtime` when the mismatch exists only in the request the program builds.

Each case gets a directory `cases/<id>/`, with the id two digits wide (`01`):

- `request.json`: the request sent to the model, as OpenAI Chat Completions,
  OpenAI Responses or Anthropic Messages. A static case is built from the
  prompt and the tool definitions at the parent commit of the fix. A runtime
  case is synthetic: it reproduces the request described by the issue or
  commit.
- `source.md`: the repository, commit and files it was taken from, and what
  was transcribed by hand (for example tool schemas written in code).
- `expected.json`: the findings the rules must produce, or why the case is not
  expected to be caught (`S` and `X` cases stay in the set as "not caught").
  Expectations are committed on their own, before the first rule, and are not
  changed afterwards except in a pull request that explains why.

### Dev and holdout

Cases are split by project, so no project is in both sets. `cases/split.tsv`
gives the split. It is not chosen by hand: projects are sorted by the SHA-256
of their name, and each one in that order joins the holdout set if the holdout
stays at 14 cases or fewer. The rest is dev: 25 cases in 12 projects, against
14 cases in 10 projects for holdout. Rules are tuned on dev only.

## Precision corpus (`corpus/`)

Requests built from the current code of 6 to 8 open-source agents at a fixed
commit, with every finding labeled by hand as a true or false positive in
`corpus/<repo>/labels.json`.

## Reference tools (`tools/`)

Not part of the package and not run by the benchmark:

- `detect_prototype.py`: the prototype the reference extraction starts from.
- `hermes_render_check.py`: renders hermes-agent's prompt blocks for a given
  set of tools and lists the tools they name that the session does not have.
