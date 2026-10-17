# Notes

Assumptions made where the request or the code was ambiguous. Notes from 0.x
are in [docs/history/notes-0.x.md](docs/history/notes-0.x.md).

## Skeleton kept from 0.x

- Kept as the skeleton: the `handshake` command with `--help`, `--version` and
  `--debug`, the exit codes, config loading with the unknown-key message, and
  the generic report helpers (JUnit XML, Markdown, GitHub annotation format).
  The console and GitHub reporters that formatted spec and diff results went
  with them.
- `handshake.yaml` keeps only `project_name` and `version`; the new settings
  come with the rules. No migration messages for old settings: there is no
  compatibility with 0.x.
