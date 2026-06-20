from __future__ import annotations

import pytest

from goodreads_cli.service import (
    BookMatchAmbiguousError,
    BookNotFoundError,
    GoodreadsService,
)


class FakeSearchClient:
    def __init__(self, results):
        self.results = results

    def search_books(self, query):
        return self.results


class FakeMutationClient:
    def __init__(self):
        self.calls = []
        self.current_books_payload: list[dict[str, object]] = []

    def require_session(self) -> None:
        self.calls.append(("require_session",))

    def current_books(self) -> list[dict[str, object]]:
        self.calls.append(("current_books",))
        return self.current_books_payload

    def add_shelf(self, book_id: str, shelf: str) -> None:
        self.calls.append(("add_shelf", book_id, shelf))

    def remove_shelf(self, book_id: str, shelf: str) -> None:
        self.calls.append(("remove_shelf", book_id, shelf))

    def add_tags(self, book_id: str, tags: list[str]) -> None:
        self.calls.append(("add_tags", book_id, tags))

    def update_progress(
        self, book_id: str, *, page: int | None = None, percent: int | None = None
    ) -> None:
        self.calls.append(("update_progress", book_id, page, percent))

    def finish_book(self, book_id: str, *, rating: int, review: str | None) -> None:
        self.calls.append(("finish_book", book_id, rating, review))


def test_resolve_book_accepts_small_title_typos() -> None:
    service = GoodreadsService(
        search_client=FakeSearchClient(
            [{"id": "1", "title": "Project Hail Mary", "author": "Andy Weir", "url": ""}]
        ),
        mutation_client=None,
        presets={},
    )

    book = service.resolve_book("project hail marry")

    assert book["id"] == "1"


def test_resolve_book_rejects_weak_match() -> None:
    service = GoodreadsService(
        search_client=FakeSearchClient(
            [{"id": "1", "title": "Completely Different Title", "author": "Other", "url": ""}]
        ),
        mutation_client=None,
        presets={},
    )

    with pytest.raises(BookNotFoundError, match="Book not found: zzzznotfound"):
        service.resolve_book("zzzznotfound")


def test_resolve_book_rejects_strong_ambiguity() -> None:
    service = GoodreadsService(
        search_client=FakeSearchClient(
            [
                {"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""},
                {"id": "2", "title": "Dune", "author": "Frank Herbert", "url": ""},
            ]
        ),
        mutation_client=None,
        presets={},
    )

    with pytest.raises(BookMatchAmbiguousError, match="Book match ambiguous: dune"):
        service.resolve_book("dune")


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


def test_abandon_applies_abandoned_shelf_directly() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.abandon("Dune")

    assert payload["status"] == "abandoned"
    assert ("add_shelf", "1", "abandoned") in mutation.calls
    assert ("remove_shelf", "1", "currently-reading") not in mutation.calls


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


def test_progress_by_percent_updates_percent_only() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.progress("Dune", percent=10)

    assert payload["progress"] == {"kind": "percent", "value": 10}
    assert ("update_progress", "1", None, 10) in mutation.calls


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


def test_shelf_add_applies_single_shelf() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.shelf_add("Dune", "wishlist")

    assert payload["applied_shelves"] == ["wishlist"]
    assert ("add_tags", "1", ["wishlist"]) in mutation.calls


def test_shelf_add_uses_builtin_shelf_path_for_default_shelves() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.shelf_add("Dune", "to-read")

    assert payload["applied_shelves"] == ["to-read"]
    assert ("add_shelf", "1", "to-read") in mutation.calls


def test_tags_add_applies_multiple_shelves_in_order() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.tags_add("Dune", ["ru", "audio", "wishlist"])

    assert payload["applied_shelves"] == ["ru", "audio", "wishlist"]
    assert ("add_tags", "1", ["ru", "audio", "wishlist"]) in mutation.calls


def test_tags_add_routes_builtin_shelves_through_shelf_flow() -> None:
    mutation = FakeMutationClient()
    service = GoodreadsService(
        search_client=FakeSearchClient([{"id": "1", "title": "Dune", "author": "Frank Herbert", "url": ""}]),
        mutation_client=mutation,
        presets={},
    )

    payload = service.tags_add("Dune", ["ru", "to-read", "audio", "currently-reading"])

    assert payload["applied_shelves"] == ["ru", "to-read", "audio", "currently-reading"]
    assert ("add_tags", "1", ["ru", "audio"]) in mutation.calls
    assert ("add_shelf", "1", "to-read") in mutation.calls
    assert ("add_shelf", "1", "currently-reading") in mutation.calls


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
    assert ("add_tags", "1", ["ru", "audio", "wishlist", "sci-pop"]) in mutation.calls
    assert ("add_shelf", "1", "to-read") in mutation.calls
