# Contributing

This document describes the expected delivery workflow for `goodreads-cli`.

It is written for:

- maintainers
- external contributors
- AI coding agents

The goal is to keep the project predictable, reviewable, and release-friendly without adding unnecessary process.

## Principles

- Keep `main` stable and releasable.
- Prefer small, short-lived branches.
- Use pull requests for almost all changes.
- Keep code, tests, docs, and changelog in sync.
- Separate feature delivery from release preparation.

## Source of truth

When working on code or release tasks, use these files together:

- `AGENTS.md` for project rules
- `docs/agent-cli.md` for the agent-facing CLI contract
- `CHANGELOG.md` for release notes history
- this file for contribution and release workflow

## Recommended model

Use a lightweight trunk-based workflow:

- one permanent branch: `main`
- short-lived feature branches
- PR-based merges back into `main`
- releases created from `main`

## Day-to-day development flow

Standard flow:

1. Create or pick an issue or task.
2. Switch from `main` to a new branch.
3. Implement the change.
4. Add or update tests.
5. Update docs when the user-facing behavior changes.
6. Add changelog notes to `Unreleased` if the change is release-worthy.
7. Run validation locally.
8. Push the branch.
9. Open a PR.
10. Merge after CI passes and review is complete.

## Required updates when behavior changes

When a change affects users, maintainers, or agents, update the relevant docs in the same PR.

Common files:

- `README.md`
- `docs/agent-cli.md`
- `docs/skill.md`
- `AGENTS.md`
- `CHANGELOG.md`

## Testing expectations

Use TDD for user-facing features whenever practical.

Minimum expectations for code changes:

- add or update tests
- keep `pytest` green
- keep `ruff` green
- ensure the package still builds

Recommended local checks:

```bash
python -m pytest
python -m ruff check .
python -m build
python -m compileall src tests
```

Or:

```bash
make check
```

## Pull request workflow

PRs should be:

- focused
- small enough to review
- linked to an issue when possible
- accompanied by updated tests and docs

Suggested PR body pattern:

```text
## Summary
- add ...
- update ...

## Testing
- pytest
- python -m ruff check .
- python -m build
```

## Merge policy

Preferred merge style: `squash`.

Recommended rules:

- no direct pushes to `main`
- merge only after green CI
- use PR review for non-trivial changes

## AI agent workflow

AI agents should follow the same branch-and-PR model as humans.

Agent expectations:

- do not push directly to `main`
- do not change version numbers for ordinary feature PRs
- do not prepare a release unless explicitly asked
- update docs when behavior changes
- update tests together with code
- mention assumptions and risks in the PR description when relevant

## Versioning policy

Use semantic versioning.

For this project:

- patch: compatible fix or operational improvement
- minor: new compatible CLI capability
- major: breaking CLI or response contract changes

## Changelog policy

Use `CHANGELOG.md` continuously.

During normal feature work:

- add release-worthy notes under `Unreleased`

During release preparation:

- convert `Unreleased` notes into a versioned section
- keep the release notes concise and user-facing

## Release workflow

Do not bump the version in every feature PR.

Preferred release flow:

1. Merge feature PRs into `main`.
2. Review `CHANGELOG.md`.
3. Decide the next version.
4. Update version in:
   - `pyproject.toml`
   - `src/goodreads_cli/__init__.py`
5. Finalize release notes in `CHANGELOG.md`.
6. Run validation:
   - `pytest`
   - `ruff`
   - `build`
7. Create a release commit.
8. Create an annotated git tag `vX.Y.Z`.
9. Push `main`.
10. Push the tag.
11. Create the GitHub Release.

## In short

Normal change:

`Task -> Branch -> Code + Tests + Docs -> PR -> CI -> Merge`

Release:

`Merged work on main -> Version bump -> Changelog finalization -> Tag -> GitHub Release`
