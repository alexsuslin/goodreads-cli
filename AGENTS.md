# AGENTS.md

This repository contains a minimal Python CLI wrapper around Goodreads workflows.

The primary consumer is an external agent running on a VPS. The project should stay small, predictable, and easy for an agent to call with low prompt and context cost.

## Core goals

- Keep the CLI contract stable.
- Prefer machine-readable output over rich terminal UX.
- Add the smallest amount of code needed for each user-facing capability.
- Keep Goodreads transport details inside the codebase and docs, not in prompts.
- Document Goodreads limitations honestly. Do not pretend a modern supported public API exists if the implementation is using search endpoints plus browser automation.

## Source of truth

- Human-facing project overview: `README.md`
- Agent-facing CLI contract: `docs/agent-cli.md`
- Delivery workflow: `CONTRIBUTING.md`
- Historical skill notes / lightweight summary: `docs/skill.md`

When these documents disagree, treat `docs/agent-cli.md` as the canonical CLI contract and `CONTRIBUTING.md` as the canonical delivery workflow, then update the others to match.

## Architecture guidelines

- `src/goodreads_cli/cli.py`: argument parsing, output formatting, exit codes
- `src/goodreads_cli/service.py`: use-case logic, conservative book resolution, preset application
- `src/goodreads_cli/client.py`: Goodreads HTTP search plus Playwright-backed authenticated mutations
- `src/goodreads_cli/config.py`: env, `.env`, XDG paths, preset config loading

Keep responsibilities narrow. Avoid adding heavier abstractions until a second use case clearly needs them.

## CLI rules

- Prefer `--json` for agent usage.
- Preserve output shape compatibility where practical.
- Return exit code `0` on success and `1` on operational errors.
- Reject weak or ambiguous fuzzy matches rather than silently picking a risky book.
- Treat Goodreads custom shelves and tags as the same practical tagging model in `v0`.
- If Goodreads UI behavior changes, return explicit errors instead of pretending a mutation succeeded.

## Testing rules

- Use TDD for user-facing functionality.
- Add or update tests before or alongside behavior changes.
- Cover service behavior and CLI behavior for each new command or flag.
- Keep tests deterministic and small.
- Mock HTTP and browser transport in CI.

## Dependency rules

- Prefer the standard library unless a dependency clearly reduces complexity.
- New dependencies must have a narrow purpose.
- `requests` and `playwright` are justified by the chosen hybrid Goodreads integration path.

## Documentation update policy

When adding or changing user-facing functionality, review and update these files as needed in the same change:

- `README.md`
- `CHANGELOG.md` for release-worthy user-visible changes
- `docs/agent-cli.md`
- `CONTRIBUTING.md`
- `docs/skill.md`
- `AGENTS.md` if project conventions or maintenance rules changed

At minimum, every new CLI command or flag should be reflected in:

- command examples
- expected JSON shape or behavior notes
- any new operational caveats

## Operational notes

- The CLI supports `.env` with `GOODREADS_EMAIL` / `GOODREADS_PASSWORD` or legacy lowercase `email` / `password`.
- The CLI also supports XDG-style config at `$XDG_CONFIG_HOME/goodreads-cli/.env` and `~/.config/goodreads-cli/.env`.
- `GOODREADS_CLI_EMAIL` and `GOODREADS_CLI_PASSWORD` are valid aliases for login credentials.
- Session storage defaults to `$XDG_CONFIG_HOME/goodreads-cli/session.json` or `~/.config/goodreads-cli/session.json`.
- Preset groups load from `GOODREADS_CONFIG_FILE`, `./goodreads.toml`, `$XDG_CONFIG_HOME/goodreads-cli/config.toml`, or `~/.config/goodreads-cli/config.toml`.
- Login and write operations may fail because Goodreads or Amazon changes the UI, requires CAPTCHA, or requires 2FA.

## Change checklist

Before considering work complete:

- run tests
- run lint
- verify package build
- update docs for any CLI/API contract changes
- update `CHANGELOG.md` for release-worthy changes
- avoid committing secrets or `.env`
