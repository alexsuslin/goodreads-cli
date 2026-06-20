# Current Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `goodreads current --json` command that returns the authenticated user's `currently-reading` shelf through the CLI.

**Architecture:** Extend the existing CLI/service/client layering with a small read-only path. The CLI adds a top-level `current` command, the service adds a `current_books()` use case that requires a saved session, and the browser client adds a session-backed shelf reader that parses Goodreads' `review/list?shelf=currently-reading` page into a stable JSON-ready shape.

**Tech Stack:** Python 3.11+, argparse, Playwright, pytest, ruff

---

## Planned File Changes

- Modify: `src/goodreads_cli/cli.py`
  Responsibility: add the `current` command and dispatch it to the service
- Modify: `src/goodreads_cli/service.py`
  Responsibility: add the `current_books()` read-only use case and keep session handling consistent
- Modify: `src/goodreads_cli/client.py`
  Responsibility: add the authenticated current-reading shelf reader and page parsing
- Modify: `tests/test_cli.py`
  Responsibility: cover CLI JSON output shape and service dispatch for `current`
- Modify: `tests/test_service.py`
  Responsibility: cover service delegation and required session behavior
- Modify: `tests/test_client.py`
  Responsibility: cover client delegation and page parsing behavior
- Modify: `README.md`
  Responsibility: document the new command in the overview and command examples
- Modify: `docs/agent-cli.md`
  Responsibility: document the command, JSON shape, and session expectations
- Modify: `CHANGELOG.md`
  Responsibility: record the new user-visible CLI capability

## Task 0: Create The Feature Branch

**Files:**
- Verify only

- [ ] **Step 1: Create and switch to the implementation branch**

Run:

```bash
git checkout -b feat/current-reading-command
```

Expected:

```text
Switched to a new branch 'feat/current-reading-command'
```

## Task 1: Add The Failing Service And CLI Tests

**Files:**
- Modify: `tests/test_service.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add the failing service test for `current_books()`**

```python
def test_current_books_reads_currently_reading_shelf() -> None:
    mutation = FakeMutationClient()
    mutation.current_books_payload = [
        {
            "id": "1",
            "title": "Dune",
            "author": "Frank Herbert",
            "url": "https://www.goodreads.com/book/show/1-dune",
            "progress": {"page": None, "percent": None},
        }
    ]
    service = GoodreadsService(
        search_client=FakeSearchClient([]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.current_books()

    assert payload == {
        "shelf": "currently-reading",
        "books": [
            {
                "id": "1",
                "title": "Dune",
                "author": "Frank Herbert",
                "url": "https://www.goodreads.com/book/show/1-dune",
                "progress": {"page": None, "percent": None},
            }
        ],
    }
    assert ("require_session",) in mutation.calls
    assert ("current_books",) in mutation.calls
```

- [ ] **Step 2: Extend `FakeMutationClient` with the missing current-books hook**

```python
class FakeMutationClient:
    def __init__(self):
        self.calls = []
        self.current_books_payload: list[dict[str, object]] = []

    def current_books(self) -> list[dict[str, object]]:
        self.calls.append(("current_books",))
        return self.current_books_payload
```

- [ ] **Step 3: Add the failing CLI JSON-envelope test**

```python
def test_current_json_envelope(capsys) -> None:
    class CurrentService(FakeService):
        def current_books(self):
            self.calls.append(("current_books",))
            return {
                "shelf": "currently-reading",
                "books": [
                    {
                        "id": "1",
                        "title": "Dune",
                        "author": "Frank Herbert",
                        "url": "https://www.goodreads.com/book/show/1-dune",
                        "progress": {"page": None, "percent": None},
                    }
                ],
            }

    service = CurrentService()
    code = run(["current", "--json"], service=service)
    captured = json.loads(capsys.readouterr().out)

    assert code == 0
    assert ("current_books",) in service.calls
    assert captured == {
        "ok": True,
        "data": {
            "shelf": "currently-reading",
            "books": [
                {
                    "id": "1",
                    "title": "Dune",
                    "author": "Frank Herbert",
                    "url": "https://www.goodreads.com/book/show/1-dune",
                    "progress": {"page": None, "percent": None},
                }
            ],
        },
    }
```

- [ ] **Step 4: Run the targeted tests and verify they fail for the expected reason**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_service.py tests/test_cli.py -k current -v
```

Expected:

```text
FAIL ... AttributeError / Unsupported command / missing current_books behavior
```

- [ ] **Step 5: Commit the red test state**

```bash
git add tests/test_service.py tests/test_cli.py
git commit -m "test: cover current reading command"
```

## Task 2: Add The Failing Client Tests For Authenticated Shelf Reading

**Files:**
- Modify: `tests/test_client.py`

- [ ] **Step 1: Add browser-client delegation coverage**

```python
def test_browser_client_reads_current_books_using_saved_session(tmp_path: Path) -> None:
    adapter = FakeBrowserAdapter()
    adapter.current_books_payload = [
        {
            "id": "1",
            "title": "Dune",
            "author": "Frank Herbert",
            "url": "https://www.goodreads.com/book/show/1-dune",
            "progress": {"page": None, "percent": None},
        }
    ]
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=adapter)
    client.login(headless=True)

    payload = client.current_books()

    assert payload == adapter.current_books_payload
    assert ("current_books",) in adapter.calls
```

- [ ] **Step 2: Extend the fake browser adapter with the missing hook**

```python
class FakeBrowserAdapter:
    def __init__(self):
        self.calls = []
        self.storage_state = {"cookies": [{"name": "session", "value": "abc"}], "origins": []}
        self.current_books_payload: list[dict[str, object]] = []

    def current_books(self, *, storage_state):
        self.calls.append(("current_books",))
        return self.current_books_payload
```

- [ ] **Step 3: Add a parser-level adapter test using a fake page**

```python
class FakeShelfPage:
    def __init__(self, payload: list[dict[str, object]]):
        self.payload = payload

    def evaluate(self, script: str) -> list[dict[str, object]]:
        return self.payload


def test_playwright_adapter_reads_currently_reading_shelf(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    visited = {}
    page = FakeShelfPage(
        [
            {
                "id": "1",
                "title": "Dune",
                "author": "Frank Herbert",
                "url": "https://www.goodreads.com/book/show/1-dune",
                "progress": {"page": None, "percent": None},
            }
        ]
    )

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        lambda storage_state, url, mutate: (
            visited.update({"url": url}),
            mutate(page),
        )[-1],
        raising=False,
    )

    payload = adapter.current_books(storage_state={"cookies": []})

    assert visited["url"] == "https://www.goodreads.com/review/list?shelf=currently-reading"
    assert payload == [
        {
            "id": "1",
            "title": "Dune",
            "author": "Frank Herbert",
            "url": "https://www.goodreads.com/book/show/1-dune",
            "progress": {"page": None, "percent": None},
        }
    ]
```

- [ ] **Step 4: Add a parser-failure test**

```python
def test_playwright_adapter_raises_when_current_shelf_cannot_be_parsed(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeShelfPage([])

    def fake_with_authenticated_page(storage_state, url, mutate):
        mutate(page)

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        fake_with_authenticated_page,
        raising=False,
    )
    monkeypatch.setattr(adapter, "_is_sign_in_page", lambda page: False, raising=False)

    with pytest.raises(GoodreadsClientError, match="current-reading shelf"):
        adapter.current_books(storage_state={"cookies": []})
```

- [ ] **Step 5: Run the targeted client tests and verify they fail**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_client.py -k current -v
```

Expected:

```text
FAIL ... missing current_books method on GoodreadsBrowserClient or PlaywrightAdapter
```

- [ ] **Step 6: Commit the red client-test state**

```bash
git add tests/test_client.py
git commit -m "test: cover current shelf client path"
```

## Task 3: Implement The Service And Browser Client Read Path

**Files:**
- Modify: `src/goodreads_cli/service.py`
- Modify: `src/goodreads_cli/client.py`

- [ ] **Step 1: Add the service use case**

Insert into `GoodreadsService`:

```python
    def current_books(self) -> dict[str, Any]:
        client = self._require_mutation_client()
        return {
            "shelf": "currently-reading",
            "books": client.current_books(),
        }
```

- [ ] **Step 2: Add the browser-client delegation method**

Insert into `GoodreadsBrowserClient`:

```python
    def current_books(self) -> list[dict[str, Any]]:
        storage_state = self._load_session()
        return self.adapter.current_books(storage_state=storage_state)
```

- [ ] **Step 3: Add the Playwright adapter method**

Insert into `PlaywrightAdapter`:

```python
    def current_books(self, *, storage_state) -> list[dict[str, Any]]:
        books: list[dict[str, Any]] = []

        def read(page: Any) -> None:
            if self._is_sign_in_page(page):
                raise GoodreadsClientError(
                    "Goodreads session is no longer authenticated. Run: goodreads login"
                )
            books.extend(self._parse_current_books(page))

        self._with_authenticated_page(
            storage_state,
            "https://www.goodreads.com/review/list?shelf=currently-reading",
            read,
        )
        return books
```

- [ ] **Step 4: Add sign-in detection for read paths**

Insert helper into `PlaywrightAdapter`:

```python
    @staticmethod
    def _is_sign_in_page(page: Any) -> bool:
        url = getattr(page, "url", "") or ""
        return "/user/sign_in" in url or "/ap/signin" in url
```

- [ ] **Step 5: Add the shelf-page parser**

Insert helper into `PlaywrightAdapter`:

```python
    def _parse_current_books(self, page: Any) -> list[dict[str, Any]]:
        payload = page.evaluate(
            """
            () => {
              const rows = Array.from(document.querySelectorAll("tr.bookalike.review"));
              return rows.map((row) => {
                const titleLink =
                  row.querySelector("td.field.title a[href*='/book/show/']") ||
                  row.querySelector("a.bookTitle[href*='/book/show/']");
                const authorLink =
                  row.querySelector("td.field.author a") ||
                  row.querySelector(".authorName");
                const progressCell = row.querySelector("td.field.date_read, td.field.position");
                const href = titleLink?.getAttribute("href") || "";
                const idMatch = href.match(/\\/book\\/show\\/(\\d+)/);
                return {
                  id: idMatch ? idMatch[1] : "",
                  title: titleLink?.textContent?.trim() || "",
                  author: authorLink?.textContent?.trim() || "",
                  url: href.startsWith("http") ? href : `https://www.goodreads.com${href}`,
                  progress: {
                    page: null,
                    percent: null,
                  },
                };
              });
            }
            """
        )
        if not isinstance(payload, list):
            raise GoodreadsClientError(
                "Goodreads current-reading shelf could not be parsed from the shelf page."
            )
        normalized = [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or "").strip(),
                "author": str(item.get("author") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "progress": {
                    "page": None,
                    "percent": None,
                },
            }
            for item in payload
            if str(item.get("id") or "").strip()
            and str(item.get("title") or "").strip()
        ]
        if payload and not normalized:
            raise GoodreadsClientError(
                "Goodreads current-reading shelf could not be parsed from the shelf page."
            )
        return normalized
```

- [ ] **Step 6: Run the service and client tests and verify they pass**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_service.py tests/test_client.py -k current -v
```

Expected:

```text
PASS ... current reading service and client tests
```

- [ ] **Step 7: Commit the green implementation for the read path**

```bash
git add src/goodreads_cli/service.py src/goodreads_cli/client.py tests/test_service.py tests/test_client.py
git commit -m "feat: add current reading client path"
```

## Task 4: Wire The CLI Command

**Files:**
- Modify: `src/goodreads_cli/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add the parser entry for `current`**

Update the parser setup:

```python
    current = subparsers.add_parser("current", help="List books on the currently-reading shelf.")
    current.add_argument("--json", action="store_true", dest="as_json")
```

- [ ] **Step 2: Add the command dispatch**

Insert into `run(...)` before the mutation commands:

```python
        if args.command == "current":
            return _emit_result(active_service.current_books(), as_json)
```

- [ ] **Step 3: Expand the CLI fake service if needed**

If the tests become clearer with a dedicated helper, add:

```python
    def current_books(self):
        self.calls.append(("current_books",))
        return {
            "shelf": "currently-reading",
            "books": [],
        }
```

- [ ] **Step 4: Run the targeted CLI tests and verify they pass**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/test_cli.py -k current -v
```

Expected:

```text
PASS ... current command CLI envelope
```

- [ ] **Step 5: Commit the CLI wiring**

```bash
git add src/goodreads_cli/cli.py tests/test_cli.py
git commit -m "feat: add current command"
```

## Task 5: Update Documentation And Changelog

**Files:**
- Modify: `README.md`
- Modify: `docs/agent-cli.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the command to the README command list**

Update the command bullets and quick examples:

~~~markdown
- `current`
~~~

```bash
goodreads current --json
```

- [ ] **Step 2: Add the command to the agent guide**

Insert a new section:

~~~markdown
### `current`

```bash
goodreads current --json
```

Returns the authenticated user's `currently-reading` shelf using the saved Goodreads session.
~~~

- [ ] **Step 3: Add a changelog entry**

Add under `## Unreleased`:

~~~markdown
### Added
- `goodreads current --json` for listing the authenticated user's currently-reading shelf
~~~

- [ ] **Step 4: Run a focused grep to verify docs mention the new command**

Run:

```bash
rg -n "goodreads current|`current`" README.md docs/agent-cli.md CHANGELOG.md
```

Expected:

```text
matches in README.md, docs/agent-cli.md, and CHANGELOG.md
```

- [ ] **Step 5: Commit the docs update**

```bash
git add README.md docs/agent-cli.md CHANGELOG.md
git commit -m "docs: document current reading command"
```

## Task 6: Final Verification And Pull Request Preparation

**Files:**
- Verify only

- [ ] **Step 1: Run the full test suite**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run the linter**

Run:

```bash
.\.venv\Scripts\ruff.exe check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run the build**

Run:

```bash
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m build
```

Expected:

```text
Successfully built goodreads_agent_cli-0.1.0.tar.gz and goodreads_agent_cli-0.1.0-py3-none-any.whl
```

- [ ] **Step 4: Verify working tree status before PR**

Run:

```bash
git status --short
```

Expected:

```text
only the intended implementation changes are present
```

- [ ] **Step 5: Push the branch and create the PR**

```bash
git push -u origin feat/current-reading-command
$body = @"
## Summary
- add a read-only `goodreads current --json` command
- read the authenticated `currently-reading` shelf through the saved Goodreads session
- cover the service, client, CLI, and docs updates for the new command

## Testing
- $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest
- .\.venv\Scripts\ruff.exe check .
- $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m build
"@
gh pr create --repo alexsuslin/goodreads-cli --head feat/current-reading-command --title "feat: add current reading command" --body $body
```
