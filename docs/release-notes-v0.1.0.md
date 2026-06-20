# goodreads-cli v0.1.0

Initial public release of `goodreads-cli`: a small, agent-friendly Python CLI for Goodreads workflows with stable JSON output, conservative book matching, XDG-style configuration, and browser-backed authenticated mutations.

## Highlights

- Added a compact CLI for Goodreads reading lifecycle commands:
  - `login`
  - `find`
  - `start`
  - `want`
  - `abandon`
  - `progress --page`
  - `progress --percent`
  - `finish --rating [--review]`
  - `shelf add`
  - `tags add`
  - `preset apply`
- Added stable JSON success and failure envelopes for automation:
  - success shape: `{"ok": true, "data": ...}`
  - failure shape: `{"ok": false, "error": "..."}`
- Added conservative fuzzy book resolution with explicit weak-match and ambiguity failures instead of risky auto-picks.
- Added XDG-style configuration discovery for credentials, session state, and preset TOML files.
- Added a hybrid Goodreads transport:
  - lightweight HTTP autocomplete for `find`
  - Playwright-backed authenticated writes for login and mutations
- Added GitHub Actions CI, contributor docs, agent docs, and release hygiene files.

## Goodreads Behavior Notes

- `progress` now uses Goodreads' authenticated `user_status` write path from the current web app instead of a brittle review-edit scrape.
- Builtin shelves such as `to-read`, `currently-reading`, `read`, and `abandoned` use the shelf/status flow.
- Custom shelves and tags use Goodreads' current tagging mutation path.
- `abandon` maps to Goodreads' current `Did Not Finish` shelf/status behavior.
- Mutation commands retry one timeout-like browser failure before surfacing an error.
- Unexpected browser-adapter exceptions are wrapped as stable Goodreads client errors.

## Configuration and Runtime

- Supported credential sources, in precedence order:
  1. environment variables
  2. `./.env`
  3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
  4. `~/.config/goodreads-cli/.env`
- Supported credential names:
  - `GOODREADS_EMAIL`
  - `GOODREADS_PASSWORD`
  - `GOODREADS_CLI_EMAIL`
  - `GOODREADS_CLI_PASSWORD`
  - legacy lowercase `email` / `password`
- Supported config/session overrides:
  - `GOODREADS_CONFIG_FILE`
  - `GOODREADS_SESSION_FILE`
- Presets are loaded from TOML and expand into deterministic ordered shelf/tag application.

## Ubuntu and Headless Usage

- Headless mode is intended to work on Ubuntu without a GUI.
- Chromium system dependencies are still required.
- Recommended setup:

```bash
python -m playwright install --with-deps chromium
```

## Verification

Verified locally before release:

- `python -m pytest` -> 34 passed
- `python -m ruff check .` -> passed
- `python -m build` -> passed
- `python -m compileall src tests` -> passed

Live Goodreads verification was also performed for:

- `login`
- `find`
- `want`
- `start`
- `progress --page`
- `progress --percent`
- `tags add`
- `shelf add`
- `abandon`
- `preset apply`

The live test book was returned to `currently-reading` after verification.

## Known Limitations

- Goodreads does not provide a dependable modern official API path for this workflow, so authenticated writes depend on browser automation.
- `login` remains the most failure-prone step because Goodreads or Amazon may require CAPTCHA, 2FA, or UI-specific interaction.
- Future Goodreads UI changes may require selector or mutation-path updates even when the CLI contract remains stable.
