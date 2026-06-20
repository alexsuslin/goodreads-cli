# Goodreads CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a release-ready `goodreads-cli` repository in the style of `myshows-cli`, with stable JSON output, XDG-style config, Goodreads search plus browser-backed mutations, preset groups, tests, CI, and English documentation.

**Architecture:** Keep the codebase small and layered: `config.py` loads secrets, paths, and presets; `client.py` handles Goodreads HTTP search and Playwright-backed authenticated mutations; `service.py` resolves books conservatively and implements reading lifecycle use cases; `cli.py` owns parsing, JSON envelopes, human-readable output, and exit codes. Mutations operate only through a saved browser session; no fake OAuth or unsupported API flow is exposed.

**Tech Stack:** Python 3.11+, `requests`, `playwright`, `pytest`, `ruff`, `build`, stdlib `tomllib`

---

## Planned File Structure

### Core package files

- Create: `src/goodreads_cli/__init__.py`
  Responsibility: package version string only
- Create: `src/goodreads_cli/cli.py`
  Responsibility: argparse tree, result/error envelopes, command dispatch, text formatting
- Create: `src/goodreads_cli/client.py`
  Responsibility: Goodreads HTTP search, Playwright login/session persistence, shelf/progress/review mutations
- Create: `src/goodreads_cli/config.py`
  Responsibility: `.env` precedence, XDG path discovery, preset TOML loading, session/config path overrides
- Create: `src/goodreads_cli/service.py`
  Responsibility: fuzzy book resolution, lifecycle operations, preset expansion, safe mutation flow

### Tests

- Create: `tests/test_smoke.py`
  Responsibility: package import / version smoke test
- Create: `tests/test_config.py`
  Responsibility: env precedence, XDG loading, aliases, preset TOML loading, path overrides
- Create: `tests/test_client.py`
  Responsibility: HTTP search parsing, session save/load, mutation delegation with fake browser adapter
- Create: `tests/test_service.py`
  Responsibility: fuzzy matching, ambiguity rejection, lifecycle commands, preset application
- Create: `tests/test_cli.py`
  Responsibility: parser validation, JSON envelopes, exit codes, nested subcommands

### Repo / docs / workflow

- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Create: `CHANGELOG.md`
- Create: `AGENTS.md`
- Create: `CONTRIBUTING.md`
- Create: `docs/agent-cli.md`
- Create: `docs/skill.md`

## Task 1: Bootstrap The Repository Skeleton

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `src/goodreads_cli/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
from goodreads_cli import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'goodreads_cli'`

- [ ] **Step 3: Create the minimal package and packaging files**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling>=1.26"]
build-backend = "hatchling.build"

[project]
name = "goodreads-agent-cli"
version = "0.1.0"
description = "Minimal Goodreads CLI for agent workflows."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "OpenAI Codex" }]
dependencies = [
  "playwright>=1.54,<2",
  "requests>=2.32,<3",
]

[project.optional-dependencies]
dev = [
  "build>=1.2",
  "pytest>=9.0,<10",
  "ruff>=0.12,<1",
]

[project.scripts]
goodreads = "goodreads_cli.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--basetemp=.pytest_tmp"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["E501"]

[tool.hatch.build.targets.wheel]
packages = ["src/goodreads_cli"]
```

```python
# src/goodreads_cli/__init__.py
"""Minimal Goodreads CLI package."""

__version__ = "0.1.0"
```

```makefile
# Makefile
.PHONY: test lint build check

test:
	python -m pytest

lint:
	python -m ruff check .

build:
	python -m build

check:
	python -m compileall src tests
	python -m pytest
	python -m ruff check .
	python -m build
```

```gitignore
# .gitignore
.env
.pytest_cache/
.pytest_tmp/
.ruff_cache/
dist/
build/
*.egg-info/
__pycache__/
playwright/.local-browsers/
```

- [ ] **Step 4: Re-run the smoke test**

Run: `python -m pytest tests/test_smoke.py -v`

Expected: PASS

- [ ] **Step 5: Initialize git and commit the bootstrap**

```bash
git init
git add .gitignore Makefile pyproject.toml src/goodreads_cli/__init__.py tests/test_smoke.py
git commit -m "chore: bootstrap goodreads cli package"
```

## Task 2: Implement Config Loading, XDG Paths, And Preset TOML Support

**Files:**
- Create: `src/goodreads_cli/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing configuration tests**

```python
# tests/test_config.py
from pathlib import Path

from goodreads_cli.config import Settings


def test_settings_accept_cli_env_aliases(monkeypatch) -> None:
    monkeypatch.delenv("GOODREADS_EMAIL", raising=False)
    monkeypatch.delenv("GOODREADS_PASSWORD", raising=False)
    monkeypatch.setenv("GOODREADS_CLI_EMAIL", "cli@example.com")
    monkeypatch.setenv("GOODREADS_CLI_PASSWORD", "cli-secret")

    settings = Settings.from_env()

    assert settings.email == "cli@example.com"
    assert settings.password == "cli-secret"


def test_cwd_dotenv_overrides_xdg_dotenv(tmp_path: Path, monkeypatch) -> None:
    config_home = tmp_path / "config-home"
    xdg_dotenv = config_home / "goodreads-cli" / ".env"
    xdg_dotenv.parent.mkdir(parents=True)
    xdg_dotenv.write_text("GOODREADS_EMAIL=xdg@example.com\nGOODREADS_PASSWORD=xdg-secret\n", encoding="utf-8")

    workdir = tmp_path / "workspace"
    workdir.mkdir()
    (workdir / ".env").write_text("GOODREADS_EMAIL=local@example.com\nGOODREADS_PASSWORD=local-secret\n", encoding="utf-8")

    monkeypatch.chdir(workdir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    settings = Settings.from_env()

    assert settings.email == "local@example.com"
    assert settings.password == "local-secret"


def test_settings_load_presets_from_toml(tmp_path: Path, monkeypatch) -> None:
    config_home = tmp_path / "config-home"
    config_file = config_home / "goodreads-cli" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(
        '[presets.sci-pop]\n'
        'tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]\n',
        encoding="utf-8",
    )
    dotenv = config_home / "goodreads-cli" / ".env"
    dotenv.write_text("GOODREADS_EMAIL=reader@example.com\nGOODREADS_PASSWORD=secret\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.chdir(tmp_path / "workspace")
    (tmp_path / "workspace").mkdir()

    settings = Settings.from_env()

    assert settings.presets["sci-pop"] == ["ru", "audio", "wishlist", "sci-pop", "to-read"]
    assert settings.config_file == config_file


def test_settings_respect_explicit_session_path(tmp_path: Path, monkeypatch) -> None:
    session_file = tmp_path / "custom-session.json"
    monkeypatch.setenv("GOODREADS_SESSION_FILE", str(session_file))
    monkeypatch.setenv("GOODREADS_EMAIL", "reader@example.com")
    monkeypatch.setenv("GOODREADS_PASSWORD", "secret")

    settings = Settings.from_env()

    assert settings.session_file == session_file
```

- [ ] **Step 2: Run the config tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `goodreads_cli.config`

- [ ] **Step 3: Implement the minimal config loader**

```python
# src/goodreads_cli/config.py
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when required settings are missing."""


@dataclass(slots=True)
class Settings:
    email: str
    password: str
    session_file: Path
    config_file: Path | None
    presets: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Settings":
        dotenv_values = _load_dotenv_values()
        email = _first_value("GOODREADS_EMAIL", dotenv_values, aliases=("GOODREADS_CLI_EMAIL", "email", "EMAIL"))
        password = _first_value("GOODREADS_PASSWORD", dotenv_values, aliases=("GOODREADS_CLI_PASSWORD", "password", "PASSWORD"))
        if not email or not password:
            raise ConfigurationError("Missing required environment variables: GOODREADS_EMAIL, GOODREADS_PASSWORD")

        config_file = _preset_config_path()
        presets = _load_presets(config_file) if config_file else {}
        return cls(
            email=email,
            password=password,
            session_file=_session_file_path(),
            config_file=config_file,
            presets=presets,
        )


def _load_dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in _dotenv_paths():
        values.update(_load_dotenv(path))
    return values


def _dotenv_paths() -> list[Path]:
    paths: list[Path] = []
    config_home = os.getenv("XDG_CONFIG_HOME", "").strip()
    if config_home:
        paths.append(Path(config_home) / "goodreads-cli" / ".env")
    else:
        paths.append(_home_config_dir() / ".env")
    paths.append(Path.cwd() / ".env")
    return paths


def _preset_config_path() -> Path | None:
    explicit = os.getenv("GOODREADS_CONFIG_FILE", "").strip()
    candidates = [Path(explicit)] if explicit else [Path.cwd() / "goodreads.toml", *_default_config_candidates("config.toml")]
    for path in candidates:
        if path.exists():
            return path
    return None


def _session_file_path() -> Path:
    explicit = os.getenv("GOODREADS_SESSION_FILE", "").strip()
    if explicit:
        return Path(explicit)
    return _default_config_candidates("session.json")[0]


def _home_config_dir() -> Path:
    home = os.getenv("HOME", "").strip()
    return (Path(home) if home else Path.home()) / ".config" / "goodreads-cli"


def _default_config_candidates(filename: str) -> list[Path]:
    candidates: list[Path] = []
    config_home = os.getenv("XDG_CONFIG_HOME", "").strip()
    if config_home:
        candidates.append(Path(config_home) / "goodreads-cli" / filename)
    candidates.append(_home_config_dir() / filename)
    return candidates


def _load_presets(path: Path) -> dict[str, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    presets: dict[str, list[str]] = {}
    for name, payload in raw.get("presets", {}).items():
        tags = payload.get("tags", [])
        presets[name] = [str(tag).strip() for tag in tags if str(tag).strip()]
    return presets


def _first_value(primary: str, dotenv_values: dict[str, str], aliases: tuple[str, ...] = ()) -> str:
    for key in (primary, *aliases):
        env_value = os.getenv(key)
        if env_value and env_value.strip():
            return env_value.strip()
        file_value = dotenv_values.get(key)
        if file_value and file_value.strip():
            return file_value.strip()
    return ""


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values
```

- [ ] **Step 4: Run the config tests again**

Run: `python -m pytest tests/test_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit the config work**

```bash
git add src/goodreads_cli/config.py tests/test_config.py
git commit -m "feat: add config loading and preset support"
```

## Task 3: Add Goodreads Search Client And Conservative Book Resolution

**Files:**
- Create: `src/goodreads_cli/client.py`
- Create: `src/goodreads_cli/service.py`
- Create: `tests/test_client.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Write failing search and resolution tests**

```python
# tests/test_client.py
from goodreads_cli.client import GoodreadsSearchClient


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_search_client_maps_autocomplete_payload() -> None:
    payload = [{"bookId": "54493401", "title": "Project Hail Mary", "author": {"name": "Andy Weir"}}]

    class DummySession:
        def get(self, url, params, timeout):
            assert params == {"format": "json", "q": "project hail mary"}
            return DummyResponse(payload)

    client = GoodreadsSearchClient(session=DummySession())
    matches = client.search_books("project hail mary")

    assert matches == [
        {
            "id": "54493401",
            "title": "Project Hail Mary",
            "author": "Andy Weir",
            "url": "",
        }
    ]
```

```python
# tests/test_service.py
import pytest

from goodreads_cli.service import BookMatchAmbiguousError, BookNotFoundError, GoodreadsService


class FakeSearchClient:
    def __init__(self, results):
        self.results = results

    def search_books(self, query):
        return self.results


def test_resolve_book_accepts_small_title_typos() -> None:
    service = GoodreadsService(search_client=FakeSearchClient([
        {"id": "1", "title": "Project Hail Mary", "author": "Andy Weir", "url": ""},
    ]), mutation_client=None, presets={})

    book = service.resolve_book("project hail marry")

    assert book["id"] == "1"


def test_resolve_book_rejects_weak_match() -> None:
    service = GoodreadsService(search_client=FakeSearchClient([
        {"id": "1", "title": "Completely Different Title", "author": "Other", "url": ""},
    ]), mutation_client=None, presets={})

    with pytest.raises(BookNotFoundError, match="Book not found: zzzznotfound"):
        service.resolve_book("zzzznotfound")


def test_resolve_book_rejects_strong_ambiguity() -> None:
    service = GoodreadsService(search_client=FakeSearchClient([
        {"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""},
        {"id": "2", "title": "Dune", "author": "Frank Herbert", "url": ""},
    ]), mutation_client=None, presets={})

    with pytest.raises(BookMatchAmbiguousError, match="Book match ambiguous: dune"):
        service.resolve_book("dune")
```

- [ ] **Step 2: Run the search and resolution tests to verify they fail**

Run: `python -m pytest tests/test_client.py tests/test_service.py -v`

Expected: FAIL with missing `GoodreadsSearchClient`, `GoodreadsService`, or related errors

- [ ] **Step 3: Implement the search client and resolution logic**

```python
# src/goodreads_cli/client.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass(slots=True)
class GoodreadsSearchClient:
    base_url: str = "https://www.goodreads.com"
    session: Any = field(default_factory=requests.Session)

    def search_books(self, query: str) -> list[dict[str, str]]:
        response = self.session.get(
            f"{self.base_url}/book/auto_complete",
            params={"format": "json", "q": query},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        matches: list[dict[str, str]] = []
        for item in payload:
            matches.append(
                {
                    "id": str(item.get("bookId") or item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "author": str((item.get("author") or {}).get("name") or item.get("author_name") or ""),
                    "url": str(item.get("url") or ""),
                }
            )
        return matches
```

```python
# src/goodreads_cli/service.py
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


class GoodreadsServiceError(RuntimeError):
    """Base service error."""


class BookNotFoundError(GoodreadsServiceError):
    """Raised when a book cannot be resolved safely."""


class BookMatchAmbiguousError(GoodreadsServiceError):
    """Raised when two or more strong matches are too close."""


@dataclass(slots=True)
class GoodreadsService:
    search_client: Any
    mutation_client: Any
    presets: dict[str, list[str]]
    minimum_match_score: float = 70.0
    ambiguity_window: float = 3.0

    def find_books(self, title: str, author: str | None = None) -> dict[str, Any]:
        matches = []
        for candidate in self.search_client.search_books(title):
            score = self._book_score(title, candidate, author=author)
            matches.append({**candidate, "score": score})
        matches.sort(key=lambda item: item["score"], reverse=True)
        return {"query": title, "matches": matches}

    def resolve_book(self, title: str, author: str | None = None) -> dict[str, Any]:
        matches = self.find_books(title, author)["matches"]
        if not matches or matches[0]["score"] < self.minimum_match_score:
            raise BookNotFoundError(f"Book not found: {title}")
        if len(matches) > 1 and abs(matches[0]["score"] - matches[1]["score"]) <= self.ambiguity_window:
            raise BookMatchAmbiguousError(f"Book match ambiguous: {title}")
        return matches[0]

    @staticmethod
    def _normalize(text: str | None) -> str:
        return re.sub(r"[^a-z0-9а-я]+", "", (text or "").lower())

    def _book_score(self, query: str, item: dict[str, Any], author: str | None = None) -> float:
        query_normalized = self._normalize(query)
        title_normalized = self._normalize(item.get("title"))
        if title_normalized == query_normalized:
            score = 1000.0
        elif title_normalized.startswith(query_normalized):
            score = 700.0
        elif query_normalized in title_normalized:
            score = 500.0
        else:
            score = SequenceMatcher(None, query_normalized, title_normalized).ratio() * 100
        if author:
            author_score = SequenceMatcher(None, self._normalize(author), self._normalize(item.get("author"))).ratio() * 10
            score += author_score
        return score
```

- [ ] **Step 4: Re-run the search and resolution tests**

Run: `python -m pytest tests/test_client.py tests/test_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit the search and resolution layer**

```bash
git add src/goodreads_cli/client.py src/goodreads_cli/service.py tests/test_client.py tests/test_service.py
git commit -m "feat: add book search and resolution"
```

## Task 4: Implement Lifecycle Service Operations And Preset Application

**Files:**
- Modify: `src/goodreads_cli/service.py`
- Modify: `tests/test_service.py`

- [ ] **Step 1: Add failing lifecycle tests**

```python
# tests/test_service.py
class FakeMutationClient:
    def __init__(self):
        self.calls = []

    def require_session(self) -> None:
        self.calls.append(("require_session",))

    def add_shelf(self, book_id: str, shelf: str) -> None:
        self.calls.append(("add_shelf", book_id, shelf))

    def remove_shelf(self, book_id: str, shelf: str) -> None:
        self.calls.append(("remove_shelf", book_id, shelf))

    def update_progress(self, book_id: str, *, page: int | None = None, percent: int | None = None) -> None:
        self.calls.append(("update_progress", book_id, page, percent))

    def finish_book(self, book_id: str, *, rating: int, review: str | None) -> None:
        self.calls.append(("finish_book", book_id, rating, review))


def test_start_applies_currently_reading_shelf() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.start("Dune")

    assert payload["status"] == "currently-reading"
    assert ("add_shelf", "1", "currently-reading") in mutation.calls


def test_want_applies_to_read_shelf() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.want("Dune")

    assert payload["status"] == "to-read"
    assert ("add_shelf", "1", "to-read") in mutation.calls


def test_abandon_removes_currently_reading_and_adds_abandoned() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.abandon("Dune")

    assert payload["status"] == "abandoned"
    assert ("remove_shelf", "1", "currently-reading") in mutation.calls
    assert ("add_shelf", "1", "abandoned") in mutation.calls


def test_progress_by_page_updates_page_only() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.progress("Dune", page=123)

    assert payload["progress"] == {"kind": "page", "value": 123}
    assert ("update_progress", "1", 123, None) in mutation.calls


def test_finish_passes_rating_and_review() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.finish("Dune", rating=4, review="Excellent.")

    assert payload["rating"] == 4
    assert ("finish_book", "1", 4, "Excellent.") in mutation.calls


def test_tags_add_applies_multiple_shelves_in_order() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.tags_add("Dune", ["ru", "audio", "wishlist"])

    assert payload["applied_shelves"] == ["ru", "audio", "wishlist"]


def test_preset_apply_reads_tags_from_config() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={"sci-pop": ["ru", "audio", "wishlist", "sci-pop", "to-read"]},
    )

    payload = service.preset_apply("Dune", "sci-pop")

    assert payload["preset"] == "sci-pop"
    assert payload["applied_shelves"] == ["ru", "audio", "wishlist", "sci-pop", "to-read"]
```

- [ ] **Step 2: Run the lifecycle tests to verify they fail**

Run: `python -m pytest tests/test_service.py -v`

Expected: FAIL with missing `start`, `progress`, `finish`, `tags_add`, or `preset_apply` methods

- [ ] **Step 3: Implement the lifecycle operations**

```python
# src/goodreads_cli/service.py
    def _require_mutation_client(self) -> Any:
        if self.mutation_client is None:
            raise GoodreadsServiceError("Goodreads session not found. Run: goodreads login")
        self.mutation_client.require_session()
        return self.mutation_client

    def start(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], "currently-reading")
        return {"book": self._book_payload(book), "status": "currently-reading", "applied_shelves": ["currently-reading"]}

    def want(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], "to-read")
        return {"book": self._book_payload(book), "status": "to-read", "applied_shelves": ["to-read"]}

    def abandon(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.remove_shelf(book["id"], "currently-reading")
        client.add_shelf(book["id"], "abandoned")
        return {"book": self._book_payload(book), "status": "abandoned", "applied_shelves": ["abandoned"]}

    def progress(self, title: str, *, page: int | None = None, percent: int | None = None, author: str | None = None) -> dict[str, Any]:
        if (page is None) == (percent is None):
            raise GoodreadsServiceError("Provide exactly one of --page or --percent")
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.update_progress(book["id"], page=page, percent=percent)
        kind = "page" if page is not None else "percent"
        value = page if page is not None else percent
        return {"book": self._book_payload(book), "progress": {"kind": kind, "value": value}}

    def finish(self, title: str, *, rating: int, review: str | None = None, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.finish_book(book["id"], rating=rating, review=review)
        return {"book": self._book_payload(book), "status": "read", "rating": rating, "review": review}

    def shelf_add(self, title: str, shelf: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], shelf)
        return {"book": self._book_payload(book), "applied_shelves": [shelf]}

    def tags_add(self, title: str, tags: list[str], author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author)
        client = self._require_mutation_client()
        applied: list[str] = []
        for tag in tags:
            cleaned = tag.strip()
            if cleaned and cleaned not in applied:
                client.add_shelf(book["id"], cleaned)
                applied.append(cleaned)
        return {"book": self._book_payload(book), "applied_shelves": applied}

    def preset_apply(self, title: str, preset_name: str, author: str | None = None) -> dict[str, Any]:
        if preset_name not in self.presets:
            raise GoodreadsServiceError(f"Preset not found: {preset_name}")
        payload = self.tags_add(title, self.presets[preset_name], author=author)
        payload["preset"] = preset_name
        return payload

    @staticmethod
    def _book_payload(book: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": book["id"],
            "title": book["title"],
            "author": book.get("author", ""),
            "url": book.get("url", ""),
        }
```

- [ ] **Step 4: Re-run the lifecycle tests**

Run: `python -m pytest tests/test_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit the lifecycle service**

```bash
git add src/goodreads_cli/service.py tests/test_service.py
git commit -m "feat: add reading lifecycle service commands"
```

## Task 5: Build The CLI Contract, JSON Envelopes, And Nested Commands

**Files:**
- Create: `src/goodreads_cli/cli.py`
- Modify: `src/goodreads_cli/__init__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_cli.py
import json

from goodreads_cli.cli import run


class FakeService:
    def __init__(self):
        self.calls = []

    def find_books(self, title, author=None):
        self.calls.append(("find_books", title, author))
        return {"query": title, "matches": [{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": "", "score": 1000.0}]}

    def progress(self, title, *, page=None, percent=None, author=None):
        self.calls.append(("progress", title, page, percent, author))
        return {"book": {"id": "1", "title": "Dune", "author": "Frank Herbert"}, "progress": {"kind": "page", "value": 123}}


def test_find_json_envelope(capsys) -> None:
    code = run(["find", "Dune", "--json"], service=FakeService())
    captured = json.loads(capsys.readouterr().out)

    assert code == 0
    assert captured["ok"] is True
    assert captured["data"]["query"] == "Dune"


def test_progress_requires_exactly_one_of_page_or_percent(capsys) -> None:
    code = run(["progress", "Dune", "--page", "12", "--percent", "3", "--json"], service=FakeService())
    captured = json.loads(capsys.readouterr().out)

    assert code == 1
    assert captured["ok"] is False
    assert captured["error"] == "Provide exactly one of --page or --percent"


def test_nested_shelf_add_command_uses_service(capsys) -> None:
    class ShelfService(FakeService):
        def shelf_add(self, title, shelf, author=None):
            self.calls.append(("shelf_add", title, shelf, author))
            return {"book": {"id": "1", "title": title, "author": "Frank Herbert"}, "applied_shelves": [shelf]}

    service = ShelfService()
    code = run(["shelf", "add", "Dune", "wishlist", "--json"], service=service)
    captured = json.loads(capsys.readouterr().out)

    assert code == 0
    assert ("shelf_add", "Dune", "wishlist", None) in service.calls
    assert captured["data"]["applied_shelves"] == ["wishlist"]
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`

Expected: FAIL with `ImportError` for `goodreads_cli.cli` or missing `run`

- [ ] **Step 3: Implement the CLI entry point**

```python
# src/goodreads_cli/cli.py
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from goodreads_cli.client import GoodreadsBrowserClient, GoodreadsSearchClient
from goodreads_cli.config import ConfigurationError, Settings
from goodreads_cli.service import GoodreadsService, GoodreadsServiceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goodreads", description="Minimal Goodreads CLI for agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login", help="Authenticate and store a Goodreads session.")
    login.add_argument("--json", action="store_true", dest="as_json")
    login.add_argument("--no-headless", action="store_true")

    start = subparsers.add_parser("start", help="Mark a book as currently reading.")
    start.add_argument("book_title")
    start.add_argument("--author")
    start.add_argument("--json", action="store_true", dest="as_json")

    progress = subparsers.add_parser("progress", help="Update reading progress.")
    progress.add_argument("book_title")
    progress.add_argument("--author")
    progress.add_argument("--page", type=int)
    progress.add_argument("--percent", type=int)
    progress.add_argument("--json", action="store_true", dest="as_json")

    finish = subparsers.add_parser("finish", help="Finish a book with rating and optional review.")
    finish.add_argument("book_title")
    finish.add_argument("--author")
    finish.add_argument("--rating", type=int, required=True, choices=range(1, 6))
    finish.add_argument("--review")
    finish.add_argument("--json", action="store_true", dest="as_json")

    for name in ("want", "abandon", "find"):
        command = subparsers.add_parser(name)
        command.add_argument("book_title")
        command.add_argument("--author")
        command.add_argument("--json", action="store_true", dest="as_json")

    shelf = subparsers.add_parser("shelf")
    shelf_subparsers = shelf.add_subparsers(dest="shelf_command", required=True)
    shelf_add = shelf_subparsers.add_parser("add")
    shelf_add.add_argument("book_title")
    shelf_add.add_argument("shelf")
    shelf_add.add_argument("--author")
    shelf_add.add_argument("--json", action="store_true", dest="as_json")

    tags = subparsers.add_parser("tags")
    tags_subparsers = tags.add_subparsers(dest="tags_command", required=True)
    tags_add = tags_subparsers.add_parser("add")
    tags_add.add_argument("book_title")
    tags_add.add_argument("tags", nargs="+")
    tags_add.add_argument("--author")
    tags_add.add_argument("--json", action="store_true", dest="as_json")

    preset = subparsers.add_parser("preset")
    preset_subparsers = preset.add_subparsers(dest="preset_command", required=True)
    preset_apply = preset_subparsers.add_parser("apply")
    preset_apply.add_argument("book_title")
    preset_apply.add_argument("preset_name")
    preset_apply.add_argument("--author")
    preset_apply.add_argument("--json", action="store_true", dest="as_json")
    return parser


def run(argv: list[str] | None = None, *, service: GoodreadsService | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = getattr(args, "as_json", False)
    try:
        active_service = service or _default_service()
        if args.command == "find":
            return _emit_result(active_service.find_books(args.book_title, author=args.author), as_json)
        if args.command == "start":
            return _emit_result(active_service.start(args.book_title, author=args.author), as_json)
        if args.command == "progress":
            return _emit_result(active_service.progress(args.book_title, page=args.page, percent=args.percent, author=args.author), as_json)
        if args.command == "finish":
            return _emit_result(active_service.finish(args.book_title, rating=args.rating, review=args.review, author=args.author), as_json)
        if args.command == "want":
            return _emit_result(active_service.want(args.book_title, author=args.author), as_json)
        if args.command == "abandon":
            return _emit_result(active_service.abandon(args.book_title, author=args.author), as_json)
        if args.command == "shelf" and args.shelf_command == "add":
            return _emit_result(active_service.shelf_add(args.book_title, args.shelf, author=args.author), as_json)
        if args.command == "tags" and args.tags_command == "add":
            return _emit_result(active_service.tags_add(args.book_title, args.tags, author=args.author), as_json)
        if args.command == "preset" and args.preset_command == "apply":
            return _emit_result(active_service.preset_apply(args.book_title, args.preset_name, author=args.author), as_json)
        if args.command == "login":
            return _emit_result(active_service.mutation_client.login(headless=not args.no_headless), as_json)
        parser.error(f"Unsupported command: {args.command}")
    except (ConfigurationError, GoodreadsServiceError) as error:
        return _emit_error(str(error), as_json)
    except Exception as error:  # pragma: no cover
        return _emit_error(f"Unexpected error: {error}", as_json)
    return 0


def main() -> int:
    return run()


def _default_service() -> GoodreadsService:
    settings = Settings.from_env()
    return GoodreadsService(
        search_client=GoodreadsSearchClient(),
        mutation_client=GoodreadsBrowserClient(settings),
        presets=settings.presets,
    )


def _emit_result(data: Any, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
    else:
        print(data)
    return 0


def _emit_error(message: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    else:
        print(message, file=sys.stderr)
    return 1
```

- [ ] **Step 4: Re-run the CLI tests**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS

- [ ] **Step 5: Commit the CLI contract**

```bash
git add src/goodreads_cli/cli.py tests/test_cli.py
git commit -m "feat: add cli command contract"
```

## Task 6: Implement Session Persistence And Playwright-Backed Mutation Transport

**Files:**
- Modify: `src/goodreads_cli/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Add failing session and mutation transport tests**

```python
# tests/test_client.py
from pathlib import Path

from goodreads_cli.client import GoodreadsBrowserClient
from goodreads_cli.config import Settings


class FakeBrowserAdapter:
    def __init__(self):
        self.calls = []
        self.storage_state = {"cookies": [{"name": "session", "value": "abc"}], "origins": []}

    def login(self, *, email: str, password: str, headless: bool):
        self.calls.append(("login", email, password, headless))
        return self.storage_state

    def add_shelf(self, *, storage_state, book_id: str, shelf: str):
        self.calls.append(("add_shelf", book_id, shelf))

    def remove_shelf(self, *, storage_state, book_id: str, shelf: str):
        self.calls.append(("remove_shelf", book_id, shelf))

    def update_progress(self, *, storage_state, book_id: str, page: int | None, percent: int | None):
        self.calls.append(("update_progress", book_id, page, percent))

    def finish_book(self, *, storage_state, book_id: str, rating: int, review: str | None):
        self.calls.append(("finish_book", book_id, rating, review))


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        email="reader@example.com",
        password="secret",
        session_file=tmp_path / "session.json",
        config_file=None,
        presets={},
    )


def test_login_saves_session_state_to_disk(tmp_path: Path) -> None:
    adapter = FakeBrowserAdapter()
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=adapter)

    payload = client.login(headless=True)

    assert payload["session_file"].endswith("session.json")
    assert client.settings.session_file.exists()


def test_require_session_raises_when_session_is_missing(tmp_path: Path) -> None:
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=FakeBrowserAdapter())

    try:
        client.require_session()
    except RuntimeError as error:
        assert str(error) == "Goodreads session not found. Run: goodreads login"
    else:
        raise AssertionError("Expected RuntimeError")
```

- [ ] **Step 2: Run the client tests to verify they fail**

Run: `python -m pytest tests/test_client.py -v`

Expected: FAIL with missing `GoodreadsBrowserClient` or missing session methods

- [ ] **Step 3: Implement session persistence and transport delegation**

```python
# src/goodreads_cli/client.py
import json


class GoodreadsBrowserClient:
    def __init__(self, settings, *, adapter=None):
        self.settings = settings
        self.adapter = adapter or PlaywrightAdapter()
        self._storage_state: dict[str, Any] | None = None

    def login(self, *, headless: bool = True) -> dict[str, Any]:
        storage_state = self.adapter.login(
            email=self.settings.email,
            password=self.settings.password,
            headless=headless,
        )
        self._write_session(storage_state)
        return {"authenticated": True, "session_file": str(self.settings.session_file)}

    def require_session(self) -> None:
        self._load_session()

    def add_shelf(self, book_id: str, shelf: str) -> None:
        self.adapter.add_shelf(storage_state=self._load_session(), book_id=book_id, shelf=shelf)

    def remove_shelf(self, book_id: str, shelf: str) -> None:
        self.adapter.remove_shelf(storage_state=self._load_session(), book_id=book_id, shelf=shelf)

    def update_progress(self, book_id: str, *, page: int | None = None, percent: int | None = None) -> None:
        self.adapter.update_progress(storage_state=self._load_session(), book_id=book_id, page=page, percent=percent)

    def finish_book(self, book_id: str, *, rating: int, review: str | None) -> None:
        self.adapter.finish_book(storage_state=self._load_session(), book_id=book_id, rating=rating, review=review)

    def _load_session(self) -> dict[str, Any]:
        if self._storage_state is not None:
            return self._storage_state
        if not self.settings.session_file.exists():
            raise RuntimeError("Goodreads session not found. Run: goodreads login")
        self._storage_state = json.loads(self.settings.session_file.read_text(encoding="utf-8"))
        return self._storage_state

    def _write_session(self, storage_state: dict[str, Any]) -> None:
        self.settings.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings.session_file.write_text(json.dumps(storage_state), encoding="utf-8")
        self._storage_state = storage_state
```

```python
# src/goodreads_cli/client.py
from playwright.sync_api import sync_playwright


class PlaywrightAdapter:
    def login(self, *, email: str, password: str, headless: bool) -> dict[str, Any]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://www.goodreads.com/user/sign_in", wait_until="domcontentloaded")
            page.get_by_label("Email address").fill(email)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_load_state("networkidle")
            storage_state = context.storage_state()
            browser.close()
            return storage_state

    def add_shelf(self, *, storage_state, book_id: str, shelf: str) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()
            page.goto(f"https://www.goodreads.com/book/show/{book_id}", wait_until="domcontentloaded")
            page.get_by_role("button", name="Want to Read").click()
            page.get_by_role("menuitem", name=shelf).click()
            page.wait_for_load_state("networkidle")
            browser.close()

    def remove_shelf(self, *, storage_state, book_id: str, shelf: str) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()
            page.goto(f"https://www.goodreads.com/book/show/{book_id}", wait_until="domcontentloaded")
            page.get_by_role("button", name="Want to Read").click()
            page.get_by_role("menuitemcheckbox", name=shelf).uncheck()
            page.wait_for_load_state("networkidle")
            browser.close()

    def update_progress(self, *, storage_state, book_id: str, page: int | None, percent: int | None) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=storage_state)
            page_view = context.new_page()
            page_view.goto("https://www.goodreads.com/review/list", wait_until="domcontentloaded")
            page_view.get_by_role("link", name=book_id).click()
            if page is not None:
                page_view.get_by_label("Current page").fill(str(page))
            if percent is not None:
                page_view.get_by_label("Percent complete").fill(str(percent))
            page_view.get_by_role("button", name="Save").click()
            page_view.wait_for_load_state("networkidle")
            browser.close()

    def finish_book(self, *, storage_state, book_id: str, rating: int, review: str | None) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()
            page.goto(f"https://www.goodreads.com/book/show/{book_id}", wait_until="domcontentloaded")
            page.get_by_role("button", name="Want to Read").click()
            page.get_by_role("menuitem", name="Read").click()
            page.get_by_label("My rating").select_option(str(rating))
            if review:
                page.get_by_label("What did you think?").fill(review)
            page.get_by_role("button", name="Save").click()
            page.wait_for_load_state("networkidle")
            browser.close()
```

- [ ] **Step 4: Re-run the client tests**

Run: `python -m pytest tests/test_client.py -v`

Expected: PASS

- [ ] **Step 5: Commit the browser transport**

```bash
git add src/goodreads_cli/client.py tests/test_client.py
git commit -m "feat: add browser session transport"
```

## Task 7: Write Docs, CI, And Release Hygiene Files

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Create: `CHANGELOG.md`
- Create: `AGENTS.md`
- Create: `CONTRIBUTING.md`
- Create: `docs/agent-cli.md`
- Create: `docs/skill.md`

- [ ] **Step 1: Write the repository docs and workflow files**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
  push:
    branches:
      - main

jobs:
  checks:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: python -m pip install --upgrade pip && python -m pip install -e .[dev]
      - run: python -m compileall src tests
      - run: python -m ruff check .
      - run: python -m pytest
      - run: python -m build
```

```markdown
## Unreleased

### Added
- initial Goodreads agent CLI scaffold
- XDG-style config, preset groups, and stable JSON output
- Goodreads search plus browser-backed mutation flow
```

```markdown
# Agent Skill Notes

Use [docs/agent-cli.md](agent-cli.md) as the canonical guide for agent usage.

- use `goodreads ... --json` for automated calls
- keep Goodreads transport details inside the CLI, not in prompts
- update `docs/agent-cli.md`, `README.md`, and `AGENTS.md` whenever agent-facing behavior changes
```

~~~markdown
# Agent CLI Guide

Always prefer:

```bash
goodreads <command> ... --json
```

Source precedence:
1. environment variables
2. `./.env`
3. `$XDG_CONFIG_HOME/goodreads-cli/.env`
4. `~/.config/goodreads-cli/.env`

Preset config precedence:
1. `GOODREADS_CONFIG_FILE`
2. `./goodreads.toml`
3. `$XDG_CONFIG_HOME/goodreads-cli/config.toml`
4. `~/.config/goodreads-cli/config.toml`

Session note:
- Goodreads mutations use browser automation and require a prior `goodreads login`
- the default session file is `$XDG_CONFIG_HOME/goodreads-cli/session.json` or `~/.config/goodreads-cli/session.json`
- weak matches return `Book not found: ...`
- strong multi-match cases return `Book match ambiguous: ...`
~~~

```markdown
# AGENTS.md

This repository contains a minimal Python CLI wrapper around Goodreads workflows.

- keep the CLI contract stable
- prefer machine-readable output
- document Goodreads limitations honestly
- treat `docs/agent-cli.md` as the canonical CLI contract
```

```markdown
# Contributing

- use short-lived branches
- prefer PRs
- keep docs, tests, and changelog in sync
- do not bump the version for ordinary feature PRs
- use `CHANGELOG.md` `Unreleased` during normal work
```

~~~markdown
# goodreads-agent-cli

Minimal Python CLI wrapper around Goodreads workflows for agent use.

## Current commands

```bash
goodreads login --json
goodreads start "Project Hail Mary" --json
goodreads progress "Project Hail Mary" --page 123 --json
goodreads finish "Project Hail Mary" --rating 4 --review "Excellent." --json
goodreads preset apply "Project Hail Mary" sci-pop --json
```

## Important limitation

As of 2026-06-20, the project does not assume a supported modern Goodreads API path for new clients. Search uses lightweight HTTP behavior; authenticated writes use browser automation with a saved session.

## Presets

Store preset groups in `goodreads.toml` or XDG config:

```toml
[presets.sci-pop]
tags = ["ru", "audio", "wishlist", "sci-pop", "to-read"]
```

## Ubuntu note

Headless mode works on Ubuntu without a GUI, but Chromium system libraries are still required. Also run:

```bash
python -m playwright install chromium
```
~~~

- [ ] **Step 2: Run repository-wide validation**

Run: `python -m compileall src tests`

Expected: PASS

Run: `python -m pytest`

Expected: PASS

Run: `python -m ruff check .`

Expected: PASS

Run: `python -m build`

Expected: PASS

- [ ] **Step 3: Review spec coverage before final docs commit**

Check that the docs explicitly mention:

```text
- login command
- search + browser hybrid transport
- config precedence
- session file handling
- preset TOML configuration
- safe fuzzy matching / ambiguity behavior
- release workflow via Unreleased changelog
```

- [ ] **Step 4: Commit the docs and workflow files**

```bash
git add .github/workflows/ci.yml README.md CHANGELOG.md AGENTS.md CONTRIBUTING.md docs/agent-cli.md docs/skill.md
git commit -m "docs: add project documentation and ci"
```

- [ ] **Step 5: Create the final implementation handoff checkpoint**

```bash
git status --short
python -m pytest
python -m ruff check .
python -m build
```

Expected:

```text
working tree clean
all tests passing
ruff passing
build succeeding
```
