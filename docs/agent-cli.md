# Agent CLI Guide

This is the canonical guide for agents that use `goodreads-agent-cli`.

## Purpose

Use the CLI instead of embedding Goodreads transport details into prompts. The CLI keeps calls short, responses structured, and context usage low.

## Execution mode

Always prefer JSON mode:

```bash
goodreads <command> ... --json
```

Treat the JSON payload as the source of truth. Use exit code `0` as success and `1` as failure.

## Credentials and config precedence

The CLI reads configuration from environment variables, a local `.env`, or XDG-style config.

Credential source precedence:

1. environment variables
2. `./.env`
3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
4. `~/.config/goodreads-cli/.env`

Smallest practical `.env`:

```dotenv
GOODREADS_EMAIL=your-login-email
GOODREADS_PASSWORD=your-password
```

Explicit CLI aliases are also supported:

```dotenv
GOODREADS_CLI_EMAIL=your-login-email
GOODREADS_CLI_PASSWORD=your-password
```

Legacy lowercase aliases also work:

```dotenv
email=your-login-email
password=your-password
```

Preset config precedence:

1. `GOODREADS_CONFIG_FILE`
2. `./goodreads.toml`
3. `$XDG_CONFIG_HOME/goodreads-cli/config.toml`
4. `~/.config/goodreads-cli/config.toml`

Session file path precedence:

1. `GOODREADS_SESSION_FILE`
2. `$XDG_CONFIG_HOME/goodreads-cli/session.json`
3. `~/.config/goodreads-cli/session.json`

## Goodreads integration strategy and limitations

As of June 20, 2026, this project does not assume a supported modern Goodreads API path for new clients.

The implementation uses a hybrid approach:

- `find` uses lightweight Goodreads search/autocomplete behavior over HTTP
- `login` uses browser automation with a persisted session
- writes reuse that authenticated session and follow the Goodreads web app's current mutation paths

Behavior notes:

- `goodreads login` is required before mutation commands
- login is the most failure-prone step because Goodreads or Amazon may require CAPTCHA, 2FA, or UI-specific interaction
- the CLI should return explicit operational errors rather than silently reporting success when a write cannot be verified
- on Ubuntu without a GUI, install Chromium and its system dependencies before first use, for example with `python -m playwright install --with-deps chromium`

## Supported commands

### `login`

```bash
goodreads login --json
goodreads login --no-headless --json
```

Use this command first to establish and save an authenticated session.

### `find`

```bash
goodreads find "Project Hail Mary" --json
goodreads find "Project Hail Mary" --author "Andy Weir" --json
```

Expected success shape:

```json
{
  "ok": true,
  "data": {
    "query": "Project Hail Mary",
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

### `start`

```bash
goodreads start "Project Hail Mary" --json
```

The CLI maps this to Goodreads shelf/status behavior for `currently-reading`.

### `progress`

```bash
goodreads progress "Project Hail Mary" --page 123 --json
goodreads progress "Project Hail Mary" --percent 10 --json
```

Behavior rules:

- exactly one of `--page` or `--percent` is required
- passing both is an error
- the CLI does not silently derive the other progress field
- the CLI uses Goodreads' current authenticated `user_status` write path rather than scraping a review-edit form
- if Goodreads changes that web-app contract, the CLI should return an explicit operational error rather than a false success

### `finish`

```bash
goodreads finish "Project Hail Mary" --rating 4 --review "Excellent." --json
```

### `want`

```bash
goodreads want "Project Hail Mary" --json
```

The CLI maps this to Goodreads shelf/status behavior for `to-read`.

### `abandon`

```bash
goodreads abandon "Project Hail Mary" --json
```

The CLI maps this to Goodreads' current `Did Not Finish` shelf/status path rather than inventing a separate API state.

### `shelf add`

```bash
goodreads shelf add "Project Hail Mary" "wishlist" --json
```

Builtin shelves such as `to-read`, `currently-reading`, `read`, and `abandoned` use the shelf/status flow. Custom shelves reuse Goodreads' current tagging flow.

### `tags add`

```bash
goodreads tags add "Project Hail Mary" ru audio wishlist --json
```

Tags use Goodreads' current tagging mutation from the web app. In practice, this is the same Goodreads model used by custom shelves.

Builtin shelves named inside `tags add` or `preset apply`, such as `to-read`, still use the shelf/status flow instead of the tagging mutation.

### `preset apply`

```bash
goodreads preset apply "Project Hail Mary" "sci-pop" --json
```

Example preset config:

```toml
[presets.sci-pop]
tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]
```

## Error format

On failure:

```json
{
  "ok": false,
  "error": "human readable message"
}
```

Examples:

- `Book not found: zzzznotfound`
- `Book match ambiguous: dune`
- `Goodreads session not found. Run: goodreads login`

## Recommended agent behavior

- Prefer exact titles when available.
- Pass `--author` when a title is common.
- Prefer `--json` in automated calls.
- Run `goodreads login` before attempting mutations.
- If a weak or ambiguous match is returned, ask for clarification rather than forcing a risky write.

## Documentation maintenance rule

When a new CLI command, flag, or response field is added, update this file in the same change.
