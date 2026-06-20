from __future__ import annotations

import json

from goodreads_cli.cli import run


class FakeService:
    def __init__(self):
        self.calls = []

    def find_books(self, title, author=None):
        self.calls.append(("find_books", title, author))
        return {
            "query": title,
            "matches": [
                {
                    "id": "1",
                    "title": "Dune",
                    "author": "Frank Herbert",
                    "url": "",
                    "score": 1000.0,
                }
            ],
        }

    def progress(self, title, *, page=None, percent=None, author=None):
        self.calls.append(("progress", title, page, percent, author))
        return {
            "book": {"id": "1", "title": "Dune", "author": "Frank Herbert"},
            "progress": {"kind": "page", "value": 123},
        }


def test_find_json_envelope(capsys) -> None:
    code = run(["find", "Dune", "--json"], service=FakeService())
    captured = json.loads(capsys.readouterr().out)

    assert code == 0
    assert captured["ok"] is True
    assert captured["data"]["query"] == "Dune"


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


def test_progress_requires_exactly_one_of_page_or_percent(capsys) -> None:
    code = run(
        ["progress", "Dune", "--page", "12", "--percent", "3", "--json"],
        service=FakeService(),
    )
    captured = json.loads(capsys.readouterr().out)

    assert code == 1
    assert captured["ok"] is False
    assert captured["error"] == "Provide exactly one of --page or --percent"


def test_nested_shelf_add_command_uses_service(capsys) -> None:
    class ShelfService(FakeService):
        def shelf_add(self, title, shelf, author=None):
            self.calls.append(("shelf_add", title, shelf, author))
            return {
                "book": {"id": "1", "title": title, "author": "Frank Herbert"},
                "applied_shelves": [shelf],
            }

    service = ShelfService()
    code = run(["shelf", "add", "Dune", "wishlist", "--json"], service=service)
    captured = json.loads(capsys.readouterr().out)

    assert code == 0
    assert ("shelf_add", "Dune", "wishlist", None) in service.calls
    assert captured["data"]["applied_shelves"] == ["wishlist"]
