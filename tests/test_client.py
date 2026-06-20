from __future__ import annotations

from pathlib import Path

import pytest

from goodreads_cli.client import (
    GoodreadsBrowserClient,
    GoodreadsClientError,
    GoodreadsSearchClient,
    PlaywrightAdapter,
)
from goodreads_cli.config import Settings


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_search_client_maps_autocomplete_payload() -> None:
    payload = [
        {
            "bookId": "54493401",
            "title": "Project Hail Mary",
            "author": {"name": "Andy Weir"},
            "bookUrl": "/book/show/54493401-project-hail-mary",
        }
    ]

    class DummySession:
        def get(self, url, params, headers, timeout):
            assert url.endswith("/book/auto_complete")
            assert params == {"format": "json", "q": "project hail mary"}
            assert "Mozilla" in headers["User-Agent"]
            assert headers["Accept"] == "application/json"
            assert timeout == 20
            return DummyResponse(payload)

    client = GoodreadsSearchClient(session=DummySession())
    matches = client.search_books("project hail mary")

    assert matches == [
        {
            "id": "54493401",
            "title": "Project Hail Mary",
            "author": "Andy Weir",
            "url": "https://www.goodreads.com/book/show/54493401-project-hail-mary",
        }
    ]


class FakeBrowserAdapter:
    def __init__(self):
        self.calls = []
        self.storage_state = {"cookies": [{"name": "session", "value": "abc"}], "origins": []}
        self.current_books_payload: list[dict[str, object]] = []

    def login(self, *, email: str, password: str, headless: bool):
        self.calls.append(("login", email, password, headless))
        return self.storage_state

    def current_books(self, *, storage_state):
        self.calls.append(("current_books",))
        return self.current_books_payload

    def add_shelf(self, *, storage_state, book_id: str, shelf: str):
        self.calls.append(("add_shelf", book_id, shelf))

    def remove_shelf(self, *, storage_state, book_id: str, shelf: str):
        self.calls.append(("remove_shelf", book_id, shelf))

    def add_tags(self, *, storage_state, book_id: str, tags: list[str]):
        self.calls.append(("add_tags", book_id, tags))

    def update_progress(
        self, *, storage_state, book_id: str, page: int | None, percent: int | None
    ):
        self.calls.append(("update_progress", book_id, page, percent))

    def finish_book(self, *, storage_state, book_id: str, rating: int, review: str | None):
        self.calls.append(("finish_book", book_id, rating, review))


class FlakyBrowserAdapter(FakeBrowserAdapter):
    def __init__(self, failures: list[Exception]):
        super().__init__()
        self.failures = failures

    def add_shelf(self, *, storage_state, book_id: str, shelf: str):
        if self.failures:
            raise self.failures.pop(0)
        super().add_shelf(storage_state=storage_state, book_id=book_id, shelf=shelf)


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

    assert payload == {
        "authenticated": True,
        "session_file": str(tmp_path / "session.json"),
    }
    assert client.settings.session_file.exists()


def test_require_session_raises_when_session_is_missing(tmp_path: Path) -> None:
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=FakeBrowserAdapter())

    with pytest.raises(
        GoodreadsClientError,
        match="Goodreads session not found. Run: goodreads login",
    ):
        client.require_session()


def test_browser_client_delegates_mutations_using_saved_session(tmp_path: Path) -> None:
    adapter = FakeBrowserAdapter()
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=adapter)
    client.login(headless=True)

    client.add_shelf("1", "wishlist")
    client.remove_shelf("1", "wishlist")
    client.add_tags("1", ["ru", "audio"])
    client.update_progress("1", page=123)
    client.finish_book("1", rating=4, review="Excellent.")

    assert ("add_shelf", "1", "wishlist") in adapter.calls
    assert ("remove_shelf", "1", "wishlist") in adapter.calls
    assert ("add_tags", "1", ["ru", "audio"]) in adapter.calls
    assert ("update_progress", "1", 123, None) in adapter.calls
    assert ("finish_book", "1", 4, "Excellent.") in adapter.calls


def test_browser_client_retries_retryable_mutation_failures_once(tmp_path: Path) -> None:
    adapter = FlakyBrowserAdapter([TimeoutError("Timeout 30000ms exceeded.")])
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=adapter)
    client.login(headless=True)

    client.add_shelf("1", "wishlist")

    assert ("add_shelf", "1", "wishlist") in adapter.calls


def test_browser_client_wraps_unexpected_mutation_errors(tmp_path: Path) -> None:
    adapter = FlakyBrowserAdapter([RuntimeError("boom")])
    client = GoodreadsBrowserClient(build_settings(tmp_path), adapter=adapter)
    client.login(headless=True)

    with pytest.raises(GoodreadsClientError, match="Goodreads add shelf failed: boom"):
        client.add_shelf("1", "wishlist")


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


class FakeMetaLocator:
    def __init__(self, token: str | None):
        self.token = token

    def get_attribute(self, name: str) -> str | None:
        assert name == "content"
        return self.token


class FakeProgressPage:
    def __init__(self, *, token: str | None, response: dict[str, object] | None = None):
        self.token = token
        self.response = response or {"ok": True, "status": 200, "text": "{}"}
        self.evaluate_calls: list[tuple[str, dict[str, object]]] = []

    def locator(self, selector: str) -> FakeMetaLocator:
        assert selector == 'meta[name="csrf-token"]'
        return FakeMetaLocator(self.token)

    def evaluate(self, script: str, payload: dict[str, object]) -> dict[str, object]:
        self.evaluate_calls.append((script, payload))
        return self.response


class FakeTaggingPage:
    def __init__(
        self,
        *,
        metadata: dict[str, object] | None = None,
        response: dict[str, object] | None = None,
    ):
        self.metadata = metadata or {
            "book_id": "kca://book/amzn1.gr.book.v3.demo",
            "jwt_token": "jwt-token",
        }
        self.response = response or {"ok": True, "status": 200, "text": '{"data":{"tagBook":{}}}'}
        self.evaluate_calls: list[tuple[str, dict[str, object]]] = []

    def evaluate(self, script: str, payload: dict[str, object]) -> dict[str, object]:
        self.evaluate_calls.append((script, payload))
        if len(self.evaluate_calls) == 1:
            return self.metadata
        return self.response


class FakeShelfPage:
    def __init__(self, payload):
        self.payload = payload
        self.url = "https://www.goodreads.com/review/list?shelf=currently-reading"

    def evaluate(self, script: str):
        return self.payload


def test_playwright_adapter_updates_progress_via_user_status_endpoint(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeProgressPage(token="csrf-token")

    def fake_with_book_page(storage_state, book_id, mutate):
        mutate(page)

    def fake_with_authenticated_page(storage_state, url, mutate):
        assert url == "https://www.goodreads.com/"
        mutate(page)

    monkeypatch.setattr(adapter, "_with_book_page", fake_with_book_page)
    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        fake_with_authenticated_page,
        raising=False,
    )

    adapter.update_progress(storage_state={"cookies": []}, book_id="54493401", page=123, percent=None)

    assert len(page.evaluate_calls) == 1
    script, payload = page.evaluate_calls[0]
    assert "/user_status.json" in script
    assert payload == {
        "token": "csrf-token",
        "payload": {
            "user_status[book_id]": "54493401",
            "user_status[body]": "",
            "user_status[page]": "123",
        },
    }


def test_playwright_adapter_requires_csrf_token_for_progress(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeProgressPage(token=None)

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        lambda storage_state, url, mutate: mutate(page),
        raising=False,
    )
    monkeypatch.setattr(adapter, "_with_book_page", lambda storage_state, book_id, mutate: mutate(page))

    with pytest.raises(GoodreadsClientError, match="CSRF"):
        adapter.update_progress(storage_state={"cookies": []}, book_id="54493401", page=123, percent=None)


def test_playwright_adapter_adds_tags_via_graphql(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeTaggingPage()

    monkeypatch.setattr(adapter, "_with_book_page", lambda storage_state, book_id, mutate: mutate(page))

    adapter.add_tags(storage_state={"cookies": []}, book_id="54493401", tags=["ru", "audio"])

    assert len(page.evaluate_calls) == 2
    fetch_script, payload = page.evaluate_calls[1]
    assert "TagBook" in fetch_script
    assert "appsync-api.us-east-1.amazonaws.com/graphql" in fetch_script
    assert payload == {
        "book_id": "kca://book/amzn1.gr.book.v3.demo",
        "jwt_token": "jwt-token",
        "tags": ["ru", "audio"],
    }


def test_playwright_adapter_requires_graphql_metadata_for_tags(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeTaggingPage(metadata={"book_id": None, "jwt_token": None})

    monkeypatch.setattr(adapter, "_with_book_page", lambda storage_state, book_id, mutate: mutate(page))

    with pytest.raises(GoodreadsClientError, match="metadata"):
        adapter.add_tags(storage_state={"cookies": []}, book_id="54493401", tags=["ru"])


def test_playwright_adapter_reads_currently_reading_shelf(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    visited: dict[str, str] = {}
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

    def fake_with_authenticated_page(storage_state, url, mutate):
        visited["url"] = url
        mutate(page)

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        fake_with_authenticated_page,
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


def test_playwright_adapter_allows_empty_current_shelf(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeShelfPage([])

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        lambda storage_state, url, mutate: mutate(page),
        raising=False,
    )

    payload = adapter.current_books(storage_state={"cookies": []})

    assert payload == []


def test_playwright_adapter_raises_when_current_shelf_cannot_be_parsed(monkeypatch) -> None:
    adapter = PlaywrightAdapter()
    page = FakeShelfPage([{"title": "", "id": "", "author": "", "url": "", "progress": {}}])

    monkeypatch.setattr(
        adapter,
        "_with_authenticated_page",
        lambda storage_state, url, mutate: mutate(page),
        raising=False,
    )
    monkeypatch.setattr(adapter, "_is_sign_in_page", lambda page: False, raising=False)

    with pytest.raises(GoodreadsClientError, match="current-reading shelf"):
        adapter.current_books(storage_state={"cookies": []})


def test_playwright_adapter_uses_current_shelf_buttons_to_open_overlay() -> None:
    assert PlaywrightAdapter._shelf_overlay_openers() == [
        "Want to Read",
        "Currently Reading",
        "Read",
        "Did Not Finish",
        "More shelves",
        "Shelves",
    ]
