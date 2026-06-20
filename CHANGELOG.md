# Changelog

## Unreleased

### Added
- `goodreads current --json` for listing the authenticated user's currently-reading shelf

## 0.1.0 - 2026-06-20

### Added
- initial Goodreads agent CLI scaffold
- XDG-style config, preset groups, and stable JSON output
- Goodreads search plus browser-backed mutation flow
- stable JSON success and error envelopes for agent automation
- GitHub Actions CI, contributor workflow docs, agent usage docs, and release hygiene files
- headless Ubuntu guidance for Playwright-backed Goodreads automation

### Changed
- progress updates now use Goodreads' authenticated `user_status` web-app endpoint for `--page` and `--percent`
- builtin shelves route through the shelf/status flow, while custom shelves and tags route through Goodreads' current tagging mutation
- `abandon` applies Goodreads' `Did Not Finish` shelf directly instead of chaining an extra shelf removal first

### Fixed
- mutation commands retry one timeout-like browser failure before surfacing an error
- unexpected browser adapter exceptions are wrapped as stable Goodreads client errors
- mixed preset/tag flows such as `["cli-probe", "to-read"]` now apply builtin shelves and custom tags through the correct Goodreads paths
