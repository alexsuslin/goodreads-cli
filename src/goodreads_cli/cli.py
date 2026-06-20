"""CLI entry point for Goodreads agent CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from goodreads_cli.client import GoodreadsClientError
from goodreads_cli.config import ConfigurationError, Settings
from goodreads_cli.service import GoodreadsService, GoodreadsServiceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goodreads", description="Minimal Goodreads CLI for agents."
    )
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
            return _emit_result(
                active_service.find_books(args.book_title, author=args.author), as_json
            )
        if args.command == "start":
            return _emit_result(active_service.start(args.book_title, author=args.author), as_json)
        if args.command == "progress":
            if (args.page is None) == (args.percent is None):
                raise GoodreadsServiceError("Provide exactly one of --page or --percent")
            return _emit_result(
                active_service.progress(
                    args.book_title,
                    page=args.page,
                    percent=args.percent,
                    author=args.author,
                ),
                as_json,
            )
        if args.command == "finish":
            return _emit_result(
                active_service.finish(
                    args.book_title,
                    rating=args.rating,
                    review=args.review,
                    author=args.author,
                ),
                as_json,
            )
        if args.command == "want":
            return _emit_result(active_service.want(args.book_title, author=args.author), as_json)
        if args.command == "abandon":
            return _emit_result(
                active_service.abandon(args.book_title, author=args.author), as_json
            )
        if args.command == "shelf" and args.shelf_command == "add":
            return _emit_result(
                active_service.shelf_add(args.book_title, args.shelf, author=args.author),
                as_json,
            )
        if args.command == "tags" and args.tags_command == "add":
            return _emit_result(
                active_service.tags_add(args.book_title, args.tags, author=args.author),
                as_json,
            )
        if args.command == "preset" and args.preset_command == "apply":
            return _emit_result(
                active_service.preset_apply(
                    args.book_title,
                    args.preset_name,
                    author=args.author,
                ),
                as_json,
            )
        if args.command == "login":
            return _emit_result(
                active_service.mutation_client.login(headless=not args.no_headless),
                as_json,
            )
        parser.error(f"Unsupported command: {args.command}")
    except (ConfigurationError, GoodreadsClientError, GoodreadsServiceError) as error:
        return _emit_error(str(error), as_json)
    except Exception as error:  # pragma: no cover - last-resort agent-safe output
        return _emit_error(f"Unexpected error: {error}", as_json)
    return 0


def main() -> int:
    """Run the CLI."""
    return run()


def _default_service() -> GoodreadsService:
    from goodreads_cli.client import GoodreadsBrowserClient, GoodreadsSearchClient

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
