# Handoff

Read the [README](../README.md) for setup, the [CLI contract](agent-cli.md) before changing commands, and [CONTRIBUTING](../CONTRIBUTING.md) for delivery.

## Current state

- Adoption baseline: commit `eb291aa`.
- The Python CLI exposes Goodreads workflows for agents. The repository is at the v0.2.0 release commit.

## Verification

From the repository root, use the documented checks below.

```sh
make check
```

The [Makefile](../Makefile) runs compileall, pytest, Ruff, and the package build. The README lists direct Python equivalents.

Adoption and the handoff link were checked with doctor and a repeat preview. Project checks are pending.

## Next action

Review the adoption diff and run the relevant project checks when preparing the next change.
