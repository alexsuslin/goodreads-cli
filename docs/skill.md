# Agent Skill Notes

Use [docs/agent-cli.md](agent-cli.md) as the canonical guide for agent usage.

This file stays as a short pointer for skill-level discovery:

- use `goodreads start "<Book Title>" --json` when the user says they started a book
- use `goodreads progress "<Book Title>" --page 123 --json` or `--percent 10 --json` for updates
- use `goodreads tags add "<Book Title>" tag1 tag2 --json` or `goodreads shelf add "<Book Title>" custom-tag --json` for custom Goodreads tags/shelves
- use `goodreads ... --json` for automated calls
- keep Goodreads transport details inside the CLI, not in prompts
- update `docs/agent-cli.md`, `README.md`, and `AGENTS.md` whenever agent-facing behavior changes
