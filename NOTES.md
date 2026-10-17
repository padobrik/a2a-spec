# Notes

Assumptions made where the request or the code was ambiguous.

## Dependency bumps

- The pending dependabot PRs were reproduced on a branch instead of being
  merged on GitHub; the remote was not reachable from this environment.

## Rename to agent-handshake

- No compatibility layer for the old a2a-spec names (command, config file,
  project folder, pytest options, class names, PyPI package): the owner
  confirmed the project had no users at the time of the rename.
- `a2a-spec` stays on PyPI at 0.6.0 as it is; no further releases.
