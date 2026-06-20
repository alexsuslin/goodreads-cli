# Goodreads Current Command Design

Date: 2026-06-20
Status: Draft approved in conversation, written for review before implementation

## Goal

Add a read-only command:

```bash
goodreads current --json
```

The command should return the user's current `currently-reading` list through the CLI, using the saved Goodreads authenticated session instead of forcing agents to scrape Goodreads pages directly.

## Why This Exists

The repository already supports Goodreads mutations such as `start`, `progress`, `want`, `finish`, and `abandon`, but it does not expose a native read path for the user's current reading list.

For agent workflows, this creates an awkward gap:

- the CLI owns Goodreads session handling
- the CLI owns Goodreads transport details
- but agents still need an external Goodreads page fetch to answer "what am I currently reading?"

This command closes that gap while preserving the project's core rule: Goodreads transport and parsing details should stay inside the CLI.

## Command Contract

The new command is:

```bash
goodreads current --json
```

Initial scope:

- no positional arguments
- no custom shelf input
- primarily intended for automation via `--json`

Human-readable non-JSON output may continue to use the existing generic Python dict print behavior for now, because the issue only requires a working JSON contract.

## JSON Shape

Success envelope stays consistent with the rest of the CLI:

```json
{
  "ok": true,
  "data": {
    "shelf": "currently-reading",
    "books": [
      {
        "id": "54493401",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "url": "https://www.goodreads.com/book/show/54493401-project-hail-mary",
        "progress": {
          "page": null,
          "percent": null
        }
      }
    ]
  }
}
```

Design decision:

- always include a `progress` object
- use `null` values when Goodreads does not expose reliable page or percent data in the parsed shelf view

This keeps the response shape stable without pretending the data exists when it does not.

## Architecture

The new read path should mirror the existing CLI layering:

- `cli.py` adds the new `current` top-level command
- `service.py` adds a `current_books()` use case
- `client.py` adds a read-only authenticated shelf reader
- Playwright stays responsible for session-backed Goodreads page access

This preserves existing boundaries:

- CLI owns parsing and output
- service owns use-case semantics and session requirements
- client owns Goodreads transport and parsing

## Goodreads Integration Strategy

The command should use the saved Goodreads browser session, just like mutation commands do.

Proposed transport flow:

1. Require a saved session through `GoodreadsBrowserClient.require_session()`
2. Open Goodreads with that authenticated session
3. Load the current-reading shelf page:

```text
https://www.goodreads.com/review/list?shelf=currently-reading
```

4. Parse the visible book rows from the authenticated page
5. Return normalized structured data to the service layer

This is read-only behavior. It must not mutate Goodreads state.

## Data Extraction Rules

Each returned book should include:

- `id`
- `title`
- `author`
- `url`
- `progress`

Parsing rules:

- `id` should come from the Goodreads book link when possible
- `url` should be normalized to an absolute Goodreads URL
- `title` and `author` should be trimmed string values
- `progress.page` and `progress.percent` should be extracted only if Goodreads exposes stable values on the shelf page
- if progress is missing or ambiguous, return `null` for the corresponding fields instead of guessing

If the shelf is empty, the command should still succeed and return:

```json
{
  "ok": true,
  "data": {
    "shelf": "currently-reading",
    "books": []
  }
}
```

## Error Handling

The command must fail explicitly when it cannot safely read the shelf.

Expected error behavior:

- missing session:
  - `Goodreads session not found. Run: goodreads login`
- auth/session expired or Goodreads redirects to sign-in:
  - explicit operational Goodreads client error
- parsing failure because Goodreads changed the page shape:
  - explicit Goodreads client error describing that the current-reading shelf could not be parsed

It must not silently return an empty list for auth failures or parser failures.

## Testing Strategy

The issue requires automated CLI shape coverage, but the implementation should cover all three layers.

### CLI tests

Add coverage that:

- `goodreads current --json` dispatches to the service
- success output shape contains:
  - `ok: true`
  - `data.shelf == "currently-reading"`
  - `data.books`

### Service tests

Add coverage that:

- `current_books()` requires a saved session via the existing mutation/session client path
- the service returns:
  - `shelf: "currently-reading"`
  - `books: [...]`

### Client tests

Add coverage that:

- the authenticated current-reading page is parsed into the normalized JSON-ready structure
- missing session still raises the existing session error
- parser failures raise explicit client errors instead of returning `[]`

## Documentation Updates

Update these files:

- `README.md`
- `docs/agent-cli.md`
- `CHANGELOG.md`

Documentation should mention:

- the new `goodreads current --json` command
- that it uses the saved authenticated Goodreads session
- that it returns the current `currently-reading` list

## Scope Boundaries

This design intentionally does not add:

- generic `shelf list <name>` support
- pagination controls
- sorting or filtering flags
- write behavior
- complex human-readable formatting

Those can be added later if a broader read/listing surface becomes necessary. For now, the command should stay tightly focused on issue #1.
