# Goodreads CLI Design

Date: 2026-06-20
Status: Implemented and live-verified against Goodreads web behavior on 2026-06-20

## Goal

Create a new repository `goodreads-cli` in the style of `myshows-cli`: a small, agent-friendly Python CLI with stable JSON output, TDD-first development, XDG-style configuration, clear documentation, GitHub Actions CI, and release-oriented repository hygiene.

The CLI must support a minimal Goodreads reading lifecycle:

- start reading a book
- update reading progress by page
- update reading progress by percent
- finish a book with rating and optional review
- add a book for future reading
- abandon a book
- find a book
- add a shelf/tag to a book
- apply a preset group of shelves/tags from config

## Constraints and Non-Goals

### Constraints

- Keep the project intentionally small and predictable.
- Prefer machine-readable `--json` output.
- Use stable success and failure envelopes.
- Exit code `0` means success; exit code `1` means operational failure.
- Preserve the configuration philosophy from `myshows-cli`:
  1. environment variables
  2. `./.env`
  3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
  4. `~/.config/goodreads-cli/.env`
- Support explicit CLI credential aliases similar to `MYSHOWS_CLI_*`.
- Avoid dangerous fuzzy auto-picks. Mutation commands must fail on weak or ambiguous matches.
- Keep docs in English.

### Non-Goals

- No TUI or graphical UI.
- No attempt to emulate a nonexistent or unavailable modern official Goodreads API.
- No giant scraping system or undocumented HTML hacks.
- No live Goodreads integration tests in CI.
- No unnecessary heavy dependencies beyond what is needed for viable browser automation.

## Goodreads Integration Strategy

As of 2026-06-20, this project should treat Goodreads as a platform without a dependable official new-client API path for the required lifecycle operations.

The implementation will use a hybrid transport:

- `find` uses lightweight public-facing Goodreads search/autocomplete behavior over HTTP.
- `login` and all mutation commands use browser automation through `Playwright`.
- Authenticated browser state is persisted to a session file so normal commands do not have to log in repeatedly.

This design is based on two practical signals:

- the public reference repository `yareeh/goodreads-cli` documents a similar split between plain HTTP search and browser automation for login and shelf operations
- public reporting indicates Goodreads stopped issuing new API keys in December 2020, so this project must not pretend a normal supported API client flow exists for new integrations

The repository must document that:

- `login` is the most failure-prone step because Goodreads/Amazon may require CAPTCHA, 2FA, or anti-bot checks
- headless operation is expected to work on Ubuntu without a GUI, but Chromium system libraries are still required
- if the automation cannot safely confirm a mutation, the CLI returns an explicit operational error instead of silent success

## Architecture

The repository structure should stay close to `myshows-cli`.

```text
src/goodreads_cli/
  __init__.py
  cli.py
  client.py
  config.py
  service.py
tests/
  test_cli.py
  test_config.py
  test_service.py
docs/
  agent-cli.md
  skill.md
.github/workflows/ci.yml
README.md
CHANGELOG.md
CONTRIBUTING.md
AGENTS.md
Makefile
pyproject.toml
```

### Module responsibilities

- `cli.py`: argparse contract, `--json` output, human-readable output, exit codes
- `service.py`: use-case logic, book resolution, lifecycle operations, preset application, safe matching rules
- `client.py`: Goodreads transport, including HTTP search and Playwright-backed authenticated mutations
- `config.py`: `.env` loading, XDG-style config discovery, session path discovery, preset file loading

## CLI Contract

The initial CLI surface is:

```bash
goodreads login [--json] [--no-headless]
goodreads start "<book title>" [--author "<author>"] [--json]
goodreads progress "<book title>" --page 123 [--author "<author>"] [--json]
goodreads progress "<book title>" --percent 10 [--author "<author>"] [--json]
goodreads finish "<book title>" --rating 4 [--review "text"] [--author "<author>"] [--json]
goodreads want "<book title>" [--author "<author>"] [--json]
goodreads abandon "<book title>" [--author "<author>"] [--json]
goodreads find "<book title>" [--author "<author>"] [--json]
goodreads shelf add "<book title>" "<shelf>" [--author "<author>"] [--json]
goodreads tags add "<book title>" tag1 tag2 ... [--author "<author>"] [--json]
goodreads preset apply "<book title>" "<preset-name>" [--author "<author>"] [--json]
```

### Behavior rules

- `--json` is the primary automation mode.
- `progress` accepts exactly one of `--page` or `--percent`.
- `find` never mutates Goodreads state.
- `tags add` routes builtin shelves through Goodreads' shelf/status flow and routes custom shelves/tags through Goodreads' current tagging mutation.
- `preset apply` expands a configured preset into a deterministic ordered list of shelves/tags to apply.
- `start`, `want`, and `abandon` are modeled as Goodreads shelf/status transitions, not as fictional first-class API states.

## JSON Contract

### Success envelope

```json
{
  "ok": true,
  "data": {}
}
```

### Failure envelope

```json
{
  "ok": false,
  "error": "human readable message"
}
```

### Representative payloads

#### `find`

```json
{
  "ok": true,
  "data": {
    "query": "project hail mary",
    "matches": [
      {
        "id": "54493401",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "url": "https://www.goodreads.com/book/show/54493401-project-hail-mary",
        "score": 1000.0
      }
    ]
  }
}
```

#### `start`

```json
{
  "ok": true,
  "data": {
    "book": {
      "id": "54493401",
      "title": "Project Hail Mary",
      "author": "Andy Weir"
    },
    "status": "currently-reading",
    "applied_shelves": ["currently-reading"]
  }
}
```

#### `progress --page 123`

```json
{
  "ok": true,
  "data": {
    "book": {
      "id": "54493401",
      "title": "Project Hail Mary",
      "author": "Andy Weir"
    },
    "progress": {
      "kind": "page",
      "value": 123
    }
  }
}
```

#### `preset apply`

```json
{
  "ok": true,
  "data": {
    "book": {
      "id": "54493401",
      "title": "Project Hail Mary",
      "author": "Andy Weir"
    },
    "preset": "sci-pop",
    "applied_shelves": ["ru", "audio", "wishlist", "sci-pop", "to-read"]
  }
}
```

## Error Model

Mutation commands resolve a single book only when confidence is high enough. Otherwise they fail safely.

Primary operational errors:

- `Book not found: <query>` for weak or missing matches
- `Book match ambiguous: <query>` when multiple candidates remain strong
- `Goodreads session not found. Run: goodreads login` when an authenticated mutation is attempted without a saved session
- explicit browser or Goodreads UI failure messages when automation cannot complete or verify a write

## Book Resolution Rules

The service layer should implement tolerant but conservative title resolution:

- accept small title mistakes
- optionally use `--author` to improve ranking
- never silently choose a poor match
- permit deterministic best-match selection only when confidence is clearly above threshold
- reject weak matches with the same human-readable `Book not found: ...` message
- reject strong multi-match situations with an ambiguity error

The matching strategy should follow the spirit of `myshows-cli`: small fuzzy tolerance, stable behavior, and no magical risky auto-picks.

## Configuration

### Secret and credential sources

Configuration source precedence must be:

1. environment variables
2. `./.env`
3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
4. `~/.config/goodreads-cli/.env`

Supported secret and runtime variables:

- `GOODREADS_EMAIL`
- `GOODREADS_PASSWORD`
- `GOODREADS_CLI_EMAIL`
- `GOODREADS_CLI_PASSWORD`
- `GOODREADS_SESSION_FILE`
- `GOODREADS_CONFIG_FILE`

`GOODREADS_CLI_EMAIL` and `GOODREADS_CLI_PASSWORD` are explicit aliases for the primary credentials.

This version should not pretend that `GOODREADS_CLIENT_ID`, `GOODREADS_CLIENT_SECRET`, `GOODREADS_ACCESS_TOKEN`, or `GOODREADS_REFRESH_TOKEN` are supported first-class auth inputs if the implementation does not actually use a working Goodreads OAuth/API flow. The docs may mention them only as intentionally unsupported in `v0`.

### Preset config file

Presets live outside `.env` in a separate TOML file.

Config file discovery order:

1. `GOODREADS_CONFIG_FILE`, if set
2. `./goodreads.toml`
3. `$XDG_CONFIG_HOME/goodreads-cli/config.toml`
4. `~/.config/goodreads-cli/config.toml`

Example:

```toml
[presets.sci-pop]
tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]

[presets.nauchpop]
tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]
```

For `v0`, `tags` means Goodreads shelves to apply. This keeps the mental model honest and simple.

### Session storage

Session file discovery order:

1. `GOODREADS_SESSION_FILE`, if set
2. `$XDG_CONFIG_HOME/goodreads-cli/session.json`
3. `~/.config/goodreads-cli/session.json`

The project should create parent directories when saving session state or preset config state if they do not already exist.

## Lifecycle Behavior Mapping

The CLI needs a consistent Goodreads-facing interpretation for each command:

- `start`: apply the Goodreads shelf/status for currently reading
- `progress --page`: update reading progress by page
- `progress --percent`: update reading progress by percent
- `finish`: move to read/completed state and optionally apply rating and review
- `want`: place on the to-read shelf
- `abandon`: apply Goodreads' current `Did Not Finish` shelf/status path
- `shelf add`: apply one explicit shelf
- `tags add`: apply multiple shelves/tags using the correct built-in shelf or custom-tag mutation path
- `preset apply`: apply all shelves from the configured preset

If Goodreads changes or removes the current `Did Not Finish` path, the implementation must return an explicit operational error rather than inventing replacement semantics.

## Testing Strategy

The project is TDD-first. Tests should use mocked transport rather than live Goodreads calls.

### Required coverage

- configuration precedence
- XDG config loading
- CLI credential aliases
- preset config loading
- preset application behavior
- fuzzy book resolution
- weak-match rejection
- ambiguous-match rejection
- progress update by page
- progress update by percent
- finish with rating and review
- want-to-read behavior
- abandon behavior
- shelf add
- tags add
- CLI JSON output

### Test split

- `tests/test_config.py`: env precedence, XDG paths, alias handling, preset TOML loading, session/config path overrides
- `tests/test_service.py`: book resolution and lifecycle use cases, including preset application
- `tests/test_cli.py`: parser validation, JSON envelopes, exit codes, human-readable output

CI should not depend on Goodreads network access.

## CI and Repository Hygiene

The repository should include a free GitHub Actions workflow for pull requests that runs:

- syntax/compile checks
- lint
- tests
- build

The repository must include:

- `README.md`
- `CHANGELOG.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/agent-cli.md`
- `docs/skill.md`

Documentation should cover:

- CLI contract
- config precedence
- credential/session strategy
- Goodreads integration limitations and the chosen hybrid implementation
- preset/tag-group configuration
- contribution workflow
- release workflow

## Documentation Intent

### `README.md`

- project overview
- quickstart
- headless Ubuntu note
- install/dev commands
- honest Goodreads limitations

### `docs/agent-cli.md`

- canonical agent-facing contract
- JSON response shapes
- command behavior notes
- error expectations

### `CONTRIBUTING.md`

- feature branch workflow
- PR expectations
- test/lint/build checks
- release workflow

### `CHANGELOG.md`

- keep an `Unreleased` section
- do not bump version on every feature PR

### `AGENTS.md`

- architecture rules
- config/loading rules
- testing rules
- operational caveats
- instruction not to pretend Goodreads has a supported normal API if it does not

### `docs/skill.md`

- concise agent/tool usage summary aligned with the CLI contract

## Release and Versioning

Initial implementation should result in a release-ready repository state, but version bumps remain a separate release step.

The project should follow the `myshows-cli` workflow in spirit:

- task or issue
- feature branch
- PR
- merge
- separate release commit
- separate version bump
- tag
- GitHub Release

## Risks and Mitigations

### Goodreads UI drift

Risk:
- Goodreads or Amazon changes login or mutation flows.

Mitigation:
- keep browser automation narrowly scoped
- isolate selectors and browser flow inside `client.py`
- return explicit errors instead of fake success
- document `--no-headless` for debugging

### Anti-bot or 2FA friction

Risk:
- `login` may require user-visible interaction.

Mitigation:
- support `--no-headless`
- persist session after successful login
- document that post-login day-to-day operations are expected to be more stable than the first login

### Ambiguous search results

Risk:
- a mutation command may affect the wrong book.

Mitigation:
- conservative fuzzy thresholds
- ambiguity rejection
- optional `--author` disambiguation

## Open Decisions Resolved in This Design

- Use `Playwright` in Python rather than a separate helper process.
- Require exactly one of `--page` or `--percent` for progress updates.
- Use TOML for preset groups.
- Treat preset tags as Goodreads shelves in `v0`.
- Add an explicit `login` command.
- Keep the project close in structure and philosophy to `myshows-cli`.

## Implementation Readiness

This design is intentionally scoped for a first implementation plan. It is small enough for one repository and one initial release, while staying honest about Goodreads limitations and avoiding false API assumptions.
