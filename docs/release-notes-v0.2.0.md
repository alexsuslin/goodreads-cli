# goodreads-cli v0.2.0

`v0.2.0` adds the first read-only shelf inspection command to the CLI: `goodreads current --json`.

This release builds on the original mutation-focused workflow by letting agents and scripts ask "what am I currently reading?" without re-implementing Goodreads session handling or scraping logic outside the CLI.

## Highlights

- Added `goodreads current --json` as a new top-level command.
- Added a session-backed read path for Goodreads' authenticated `currently-reading` shelf.
- Added a stable JSON response shape for current-reading results:
  - `shelf: "currently-reading"`
  - `books: [...]`
  - `progress.page` and `progress.percent` included as stable nullable fields
- Added coverage for the new command at the CLI, service, and browser-client layers.
- Updated user-facing docs and agent-facing docs for the new command.

## New Command

```bash
goodreads current --json
```

Representative response:

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

If the shelf is empty, the command still succeeds and returns `books: []`.

## Behavior Notes

- The command is read-only. It does not mutate Goodreads state.
- It uses the saved Goodreads authenticated session, just like the existing mutation commands.
- If the session is missing, it returns the existing explicit session error:
  - `Goodreads session not found. Run: goodreads login`
- If Goodreads changes the authenticated shelf page enough to break parsing, the CLI returns an explicit operational error instead of silently returning an empty list.

## Verification

Verified for this release:

- `python -m pytest` -> 40 passed
- `python -m ruff check .` -> passed
- `python -m build` -> passed

## Compatibility

- This is a backward-compatible release.
- Existing commands and JSON envelopes remain unchanged.
- The new capability is additive, so the version advances from `0.1.0` to `0.2.0`.
