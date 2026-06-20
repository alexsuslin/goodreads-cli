# goodreads-agent-cli

[![CI](https://github.com/alexsuslin/goodreads-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/alexsuslin/goodreads-cli/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/alexsuslin/goodreads-cli)
[![License](https://img.shields.io/github/license/alexsuslin/goodreads-cli)](LICENSE)

Minimal Python CLI wrapper around Goodreads workflows for agent use.

The project is intentionally small. It focuses on a stable set of agent-friendly commands that are cheap to call and cheap to parse:

- `login`
- `current`
- `start`
- `progress`
- `finish`
- `want`
- `abandon`
- `find`
- `shelf add`
- `tags add`
- `preset apply`

Project guidance for maintainers lives in [AGENTS.md](AGENTS.md).
Canonical agent usage documentation lives in [docs/agent-cli.md](docs/agent-cli.md).
Contributor and release workflow lives in [CONTRIBUTING.md](CONTRIBUTING.md).
Project release history lives in [CHANGELOG.md](CHANGELOG.md).

## Why this shape

The main use case is a remote agent running on Ubuntu on a VPS. Instead of giving the agent Goodreads transport details, we give it one short CLI with predictable JSON output.

## Current commands

```bash
goodreads login --json
goodreads current --json
goodreads start "Project Hail Mary" --json
goodreads progress "Project Hail Mary" --page 123 --json
goodreads progress "Project Hail Mary" --percent 10 --json
goodreads finish "Project Hail Mary" --rating 4 --review "Excellent." --json
goodreads want "Project Hail Mary" --json
goodreads abandon "Project Hail Mary" --json
goodreads find "Project Hail Mary" --json
goodreads shelf add "Project Hail Mary" wishlist --json
goodreads tags add "Project Hail Mary" ru audio wishlist --json
goodreads preset apply "Project Hail Mary" sci-pop --json
```

## Important limitation

As of June 20, 2026, the project does not assume a supported modern Goodreads API path for new clients. Search uses lightweight HTTP behavior. Authenticated writes use browser automation with a saved session.

That means:

- `goodreads login` is required before mutation commands
- `goodreads current` also requires a saved Goodreads session because it reads the authenticated shelf view
- login may be affected by CAPTCHA, 2FA, or Goodreads/Amazon UI changes
- the CLI should return explicit errors when a write cannot be completed or verified
- page/percent progress updates use Goodreads' current authenticated `user_status` write path from the web app
- custom shelves and tags use Goodreads' current tagging flow from the web app

## Environment and config

Credentials can come from:

1. environment variables
2. `./.env`
3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
4. `~/.config/goodreads-cli/.env`

Example:

```dotenv
GOODREADS_EMAIL=your-login-email
GOODREADS_PASSWORD=your-password
```

Explicit aliases:

```dotenv
GOODREADS_CLI_EMAIL=your-login-email
GOODREADS_CLI_PASSWORD=your-password
```

Preset groups live in TOML, for example `goodreads.toml`:

```toml
[presets.sci-pop]
tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m playwright install chromium
```

## Ubuntu headless note

Headless mode works on Ubuntu without a GUI, but Chromium system libraries are still required. On Debian/Ubuntu hosts, the most reliable one-time setup is:

```bash
python -m playwright install --with-deps chromium
```

Browser automation is expected to work best after a successful one-time `goodreads login`, with the saved session reused by later commands.

## Development

```bash
make test
make lint
make build
make check
```

If you do not want `make`, the direct commands are:

```bash
python -m compileall src tests
python -m pytest
python -m ruff check .
python -m build
```

## Notes

- In Goodreads' current product model, custom shelves and tags are handled through the same tagging flow.
- Weak fuzzy matches are rejected on purpose.
- Strong multi-match ambiguity is rejected on purpose.
- When adding CLI functionality, update `README.md`, `docs/agent-cli.md`, and `docs/skill.md` in the same change.
