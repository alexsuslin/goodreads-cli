"""Service layer for Goodreads CLI use cases."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


class GoodreadsServiceError(RuntimeError):
    """Base service error."""


class BookNotFoundError(GoodreadsServiceError):
    """Raised when a book could not be resolved safely."""


class BookMatchAmbiguousError(GoodreadsServiceError):
    """Raised when multiple strong matches are too close."""


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
        matches = self.find_books(title, author=author)["matches"]
        if not matches or matches[0]["score"] < self.minimum_match_score:
            raise BookNotFoundError(f"Book not found: {title}")
        if len(matches) > 1 and abs(matches[0]["score"] - matches[1]["score"]) <= self.ambiguity_window:
            raise BookMatchAmbiguousError(f"Book match ambiguous: {title}")
        return matches[0]

    def current_books(self) -> dict[str, Any]:
        client = self._require_mutation_client()
        return {
            "shelf": "currently-reading",
            "books": client.current_books(),
        }

    def start(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], "currently-reading")
        return {
            "book": self._book_payload(book),
            "status": "currently-reading",
            "applied_shelves": ["currently-reading"],
        }

    def want(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], "to-read")
        return {
            "book": self._book_payload(book),
            "status": "to-read",
            "applied_shelves": ["to-read"],
        }

    def abandon(self, title: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        client.add_shelf(book["id"], "abandoned")
        return {
            "book": self._book_payload(book),
            "status": "abandoned",
            "applied_shelves": ["abandoned"],
        }

    def progress(
        self,
        title: str,
        *,
        page: int | None = None,
        percent: int | None = None,
        author: str | None = None,
    ) -> dict[str, Any]:
        if (page is None) == (percent is None):
            raise GoodreadsServiceError("Provide exactly one of --page or --percent")
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        client.update_progress(book["id"], page=page, percent=percent)
        kind = "page" if page is not None else "percent"
        value = page if page is not None else percent
        return {
            "book": self._book_payload(book),
            "progress": {"kind": kind, "value": value},
        }

    def finish(
        self,
        title: str,
        *,
        rating: int,
        review: str | None = None,
        author: str | None = None,
    ) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        client.finish_book(book["id"], rating=rating, review=review)
        return {
            "book": self._book_payload(book),
            "status": "read",
            "rating": rating,
            "review": review,
        }

    def shelf_add(self, title: str, shelf: str, author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        if self._is_builtin_shelf(shelf):
            client.add_shelf(book["id"], shelf)
        else:
            client.add_tags(book["id"], [shelf])
        return {"book": self._book_payload(book), "applied_shelves": [shelf]}

    def tags_add(self, title: str, tags: list[str], author: str | None = None) -> dict[str, Any]:
        book = self.resolve_book(title, author=author)
        client = self._require_mutation_client()
        applied: list[str] = []
        custom_tags: list[str] = []
        for tag in tags:
            cleaned = tag.strip()
            if cleaned and cleaned not in applied:
                applied.append(cleaned)
                if self._is_builtin_shelf(cleaned):
                    client.add_shelf(book["id"], cleaned)
                else:
                    custom_tags.append(cleaned)
        if custom_tags:
            client.add_tags(book["id"], custom_tags)
        return {"book": self._book_payload(book), "applied_shelves": applied}

    def preset_apply(
        self, title: str, preset_name: str, author: str | None = None
    ) -> dict[str, Any]:
        if preset_name not in self.presets:
            raise GoodreadsServiceError(f"Preset not found: {preset_name}")
        payload = self.tags_add(title, self.presets[preset_name], author=author)
        payload["preset"] = preset_name
        return payload

    def _require_mutation_client(self) -> Any:
        if self.mutation_client is None:
            raise GoodreadsServiceError("Goodreads session not found. Run: goodreads login")
        self.mutation_client.require_session()
        return self.mutation_client

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
            author_score = (
                SequenceMatcher(
                    None,
                    self._normalize(author),
                    self._normalize(item.get("author")),
                ).ratio()
                * 10
            )
            score += author_score
        return score

    @staticmethod
    def _book_payload(book: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": book["id"],
            "title": book["title"],
            "author": book.get("author", ""),
            "url": book.get("url", ""),
        }

    @staticmethod
    def _is_builtin_shelf(shelf: str) -> bool:
        return shelf.strip().lower() in {
            "to-read",
            "currently-reading",
            "read",
            "abandoned",
        }
