"""Goodreads transport clients."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import requests


class GoodreadsClientError(RuntimeError):
    """Raised for operational Goodreads transport failures."""


@dataclass(slots=True)
class GoodreadsSearchClient:
    """Search books through Goodreads autocomplete."""

    base_url: str = "https://www.goodreads.com"
    session: Any = field(default_factory=requests.Session)
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    def search_books(self, query: str) -> list[dict[str, str]]:
        response = self.session.get(
            f"{self.base_url}/book/auto_complete",
            params={"format": "json", "q": query},
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        matches: list[dict[str, str]] = []
        for item in payload:
            book_url = str(item.get("url") or item.get("bookUrl") or "")
            if book_url.startswith("/"):
                book_url = f"{self.base_url}{book_url}"
            matches.append(
                {
                    "id": str(item.get("bookId") or item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "author": str(
                        (item.get("author") or {}).get("name") or item.get("author_name") or ""
                    ),
                    "url": book_url,
                }
            )
        return matches


class GoodreadsBrowserClient:
    """Authenticated mutation client backed by a persisted browser session."""

    def __init__(self, settings: Any, *, adapter: Any | None = None):
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
        return {
            "authenticated": True,
            "session_file": str(self.settings.session_file),
        }

    def require_session(self) -> None:
        self._load_session()

    def add_shelf(self, book_id: str, shelf: str) -> None:
        self._run_mutation(
            "add shelf",
            lambda storage_state: self.adapter.add_shelf(
                storage_state=storage_state,
                book_id=book_id,
                shelf=shelf,
            ),
        )

    def remove_shelf(self, book_id: str, shelf: str) -> None:
        self._run_mutation(
            "remove shelf",
            lambda storage_state: self.adapter.remove_shelf(
                storage_state=storage_state,
                book_id=book_id,
                shelf=shelf,
            ),
        )

    def add_tags(self, book_id: str, tags: list[str]) -> None:
        self._run_mutation(
            "add tags",
            lambda storage_state: self.adapter.add_tags(
                storage_state=storage_state,
                book_id=book_id,
                tags=tags,
            ),
        )

    def update_progress(
        self, book_id: str, *, page: int | None = None, percent: int | None = None
    ) -> None:
        self._run_mutation(
            "update progress",
            lambda storage_state: self.adapter.update_progress(
                storage_state=storage_state,
                book_id=book_id,
                page=page,
                percent=percent,
            ),
        )

    def finish_book(self, book_id: str, *, rating: int, review: str | None) -> None:
        self._run_mutation(
            "finish book",
            lambda storage_state: self.adapter.finish_book(
                storage_state=storage_state,
                book_id=book_id,
                rating=rating,
                review=review,
            ),
        )

    def _load_session(self) -> dict[str, Any]:
        if self._storage_state is not None:
            return self._storage_state
        if not self.settings.session_file.exists():
            raise GoodreadsClientError("Goodreads session not found. Run: goodreads login")
        self._storage_state = json.loads(self.settings.session_file.read_text(encoding="utf-8"))
        return self._storage_state

    def _write_session(self, storage_state: dict[str, Any]) -> None:
        self.settings.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings.session_file.write_text(json.dumps(storage_state), encoding="utf-8")
        self._storage_state = storage_state

    def _run_mutation(
        self,
        operation: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        storage_state = self._load_session()
        attempts = 2
        last_error: GoodreadsClientError | None = None
        for attempt in range(attempts):
            try:
                callback(storage_state)
                return
            except GoodreadsClientError as error:
                last_error = error
                if attempt + 1 >= attempts or not self._is_retryable_error(error):
                    raise
            except Exception as error:
                wrapped = GoodreadsClientError(f"Goodreads {operation} failed: {error}")
                last_error = wrapped
                if attempt + 1 >= attempts or not self._is_retryable_error(error):
                    raise wrapped from error
        if last_error is not None:
            raise last_error

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        message = str(error)
        return "Timeout" in message or type(error).__name__ == "TimeoutError"


class PlaywrightAdapter:
    """Concrete Playwright browser automation adapter."""

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    def login(self, *, email: str, password: str, headless: bool) -> dict[str, Any]:
        with self._playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context(user_agent=self.user_agent, locale="en-US")
            page = context.new_page()
            page.goto("https://www.goodreads.com/user/sign_in", wait_until="domcontentloaded")
            self._fill_login(page, email=email, password=password)
            page.wait_for_load_state("networkidle")
            if "/ap/signin" in page.url or "/user/sign_in" in page.url:
                raise GoodreadsClientError(
                    "Goodreads sign-in did not complete. Manual verification or challenge handling may be required."
                )
            storage_state = context.storage_state()
            browser.close()
            return storage_state

    def add_shelf(self, *, storage_state, book_id: str, shelf: str) -> None:
        self._with_book_page(storage_state, book_id, lambda page: self._apply_shelf(page, shelf))

    def remove_shelf(self, *, storage_state, book_id: str, shelf: str) -> None:
        self._with_book_page(storage_state, book_id, lambda page: self._remove_shelf(page, shelf))

    def add_tags(self, *, storage_state, book_id: str, tags: list[str]) -> None:
        def mutate(book_page: Any) -> None:
            metadata = self._book_graphql_metadata(book_page, book_id)
            result = book_page.evaluate(
                """
                async ({ book_id, jwt_token, tags }) => {
                  const response = await fetch(
                    "https://kxbwmqov6jgg3daaamb744ycu4.appsync-api.us-east-1.amazonaws.com/graphql",
                    {
                      method: "POST",
                      headers: {
                        "Accept": "application/graphql-response+json,application/json;q=0.9",
                        "Authorization": jwt_token,
                        "Content-Type": "application/json",
                      },
                      body: JSON.stringify({
                        operationName: "TagBook",
                        variables: {
                          input: {
                            id: book_id,
                            tagsToApply: tags,
                          },
                        },
                        extensions: {
                          clientLibrary: {
                            name: "@apollo/client",
                            version: "4.1.6",
                          },
                        },
                        query: "mutation TagBook($input: TagBookInput!) {\\n  tagBook(input: $input) {\\n    taggings {\\n      tag {\\n        name\\n        webUrl\\n        __typename\\n      }\\n      __typename\\n    }\\n    __typename\\n  }\\n}",
                      }),
                      credentials: "same-origin",
                    }
                  );
                  const text = await response.text();
                  let payload = null;
                  try {
                    payload = JSON.parse(text);
                  } catch (error) {
                    payload = null;
                  }
                  return {
                    ok: response.ok && !(payload && payload.errors && payload.errors.length),
                    status: response.status,
                    text,
                  };
                }
                """,
                {
                    "book_id": metadata["book_id"],
                    "jwt_token": metadata["jwt_token"],
                    "tags": tags,
                },
            )
            if not result.get("ok"):
                raise GoodreadsClientError(
                    "Goodreads rejected the tag update request "
                    f"({result.get('status')}): {result.get('text', '')[:200]}"
                )

        self._with_book_page(storage_state, book_id, mutate)

    def update_progress(
        self, *, storage_state, book_id: str, page: int | None, percent: int | None
    ) -> None:
        payload = self._user_status_payload(book_id, page=page, percent=percent)

        def mutate(home_page: Any) -> None:
            token = self._csrf_token(home_page)
            result = home_page.evaluate(
                """
                async ({ token, payload }) => {
                  const response = await fetch("/user_status.json", {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                      "X-CSRF-Token": token,
                      "X-Requested-With": "XMLHttpRequest",
                    },
                    body: new URLSearchParams(payload).toString(),
                    credentials: "same-origin",
                  });
                  return {
                    ok: response.ok,
                    status: response.status,
                    text: await response.text(),
                  };
                }
                """,
                {"token": token, "payload": payload},
            )
            if not result.get("ok"):
                raise GoodreadsClientError(
                    "Goodreads rejected the progress update request "
                    f"({result.get('status')}): {result.get('text', '')[:200]}"
                )

        self._with_authenticated_page(storage_state, "https://www.goodreads.com/", mutate)

    def finish_book(
        self, *, storage_state, book_id: str, rating: int, review: str | None
    ) -> None:
        def mutate(book_page: Any) -> None:
            self._apply_shelf(book_page, "read")
            self._open_review_editor(book_page, book_id)
            self._select_first(book_page, ["My rating", "Rating"], str(rating))
            if review:
                self._fill_first(book_page, ["What did you think?", "Review"], review)
            self._click_first(book_page, ["Save", "save"])

        self._with_book_page(storage_state, book_id, mutate)

    def _playwright(self):
        from playwright.sync_api import sync_playwright

        return sync_playwright()

    def _with_book_page(self, storage_state: dict[str, Any], book_id: str, mutate) -> None:
        self._with_authenticated_page(
            storage_state,
            f"https://www.goodreads.com/book/show/{book_id}",
            mutate,
        )

    def _with_authenticated_page(self, storage_state: dict[str, Any], url: str, mutate) -> None:
        with self._playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=storage_state,
                user_agent=self.user_agent,
                locale="en-US",
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            mutate(page)
            page.wait_for_load_state("networkidle")
            browser.close()

    @staticmethod
    def _fill_login(page: Any, *, email: str, password: str) -> None:
        if page.get_by_role("button", name="Sign in with email").count():
            page.get_by_role("button", name="Sign in with email").click()
            page.wait_for_load_state("domcontentloaded")
        if page.get_by_label("Email address").count():
            page.get_by_label("Email address").fill(email)
        else:
            page.get_by_label("Email").fill(email)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()

    def _apply_shelf(self, page: Any, shelf: str) -> None:
        display_names = self._shelf_names(shelf)
        if shelf == "to-read" and page.get_by_role("button", name="Want to Read").count():
            page.get_by_role("button", name="Want to Read").click()
            return
        self._click_first(page, self._shelf_overlay_openers())
        primary_button = page.get_by_role("button", name=display_names[0])
        try:
            primary_button.first.wait_for(state="visible", timeout=10000)
            primary_button.first.click()
            return
        except Exception:
            pass
        self._click_first(page, display_names)

    def _remove_shelf(self, page: Any, shelf: str) -> None:
        self._click_first(page, self._shelf_overlay_openers())
        locator = self._first_locator(page, self._shelf_names(shelf))
        if locator is None:
            raise RuntimeError(f"Could not find Goodreads shelf control: {shelf}")
        try:
            locator.uncheck()
        except Exception:
            locator.click()

    def _open_review_editor(self, page: Any, book_id: str) -> None:
        try:
            page.goto(
                f"https://www.goodreads.com/review/edit/{book_id}",
                wait_until="domcontentloaded",
            )
        except Exception:
            self._click_first(page, ["Edit review", "Update progress", "Write a review"])

    def _click_first(self, page: Any, names: list[str]) -> None:
        locator = self._first_locator(page, names)
        if locator is None:
            raise GoodreadsClientError(f"Could not find Goodreads control: {', '.join(names)}")
        locator.click()

    def _fill_first(self, page: Any, names: list[str], value: str) -> None:
        locator = self._first_label(page, names)
        if locator is None:
            raise GoodreadsClientError(f"Could not find Goodreads input: {', '.join(names)}")
        locator.fill(value)

    def _select_first(self, page: Any, names: list[str], value: str) -> None:
        locator = self._first_label(page, names)
        if locator is None:
            raise GoodreadsClientError(f"Could not find Goodreads select: {', '.join(names)}")
        locator.select_option(value)

    @staticmethod
    def _first_locator(page: Any, names: list[str]):
        for name in names:
            for factory in (
                lambda: page.get_by_role("button", name=name),
                lambda: page.get_by_role("link", name=name),
                lambda: page.get_by_role("menuitem", name=name),
                lambda: page.get_by_role("menuitemcheckbox", name=name),
                lambda: page.get_by_text(name, exact=False),
            ):
                locator = factory()
                if locator.count():
                    return locator.first
        return None

    @staticmethod
    def _first_label(page: Any, names: list[str]):
        for name in names:
            locator = page.get_by_label(name)
            if locator.count():
                return locator.first
        return None

    @staticmethod
    def _shelf_names(shelf: str) -> list[str]:
        normalized = shelf.strip().lower()
        if normalized == "to-read":
            return ["Want to Read", "to-read", "to read"]
        if normalized == "currently-reading":
            return ["Currently Reading", "currently reading", "currently-reading"]
        if normalized == "read":
            return ["Read", "read"]
        if normalized == "abandoned":
            return ["Did Not Finish", "did not finish", "abandoned"]
        spaced = normalized.replace("-", " ")
        title_spaced = " ".join(part.capitalize() for part in spaced.split())
        return [shelf, spaced, title_spaced]

    @staticmethod
    def _shelf_overlay_openers() -> list[str]:
        return [
            "Want to Read",
            "Currently Reading",
            "Read",
            "Did Not Finish",
            "More shelves",
            "Shelves",
        ]

    @staticmethod
    def _csrf_token(page: Any) -> str:
        token = page.locator('meta[name="csrf-token"]').get_attribute("content")
        if not token:
            raise GoodreadsClientError("Goodreads page did not expose a CSRF token for progress updates.")
        return token

    @staticmethod
    def _user_status_payload(
        book_id: str, *, page: int | None, percent: int | None
    ) -> dict[str, str]:
        payload = {
            "user_status[book_id]": str(book_id),
            "user_status[body]": "",
        }
        if page is not None:
            payload["user_status[page]"] = str(page)
        if percent is not None:
            payload["user_status[percent]"] = str(percent)
        return payload

    @staticmethod
    def _book_graphql_metadata(page: Any, legacy_book_id: str) -> dict[str, str]:
        metadata = page.evaluate(
            """
            ({ legacyBookId }) => {
              const nextDataNode = document.getElementById("__NEXT_DATA__");
              if (!nextDataNode) {
                return { book_id: null, jwt_token: null };
              }
              const payload = JSON.parse(nextDataNode.textContent);
              const pageProps = payload?.props?.pageProps || {};
              const apolloState = pageProps.apolloState || {};
              const rootQuery = apolloState.ROOT_QUERY || {};
              const queryKey = `getBookByLegacyId({"legacyId":"${legacyBookId}"})`;
              const bookRef = rootQuery?.[queryKey]?.__ref || null;
              return {
                book_id: apolloState?.[bookRef]?.id || null,
                jwt_token: pageProps.jwtToken || null,
              };
            }
            """,
            {"legacyBookId": str(legacy_book_id)},
        )
        if not metadata.get("book_id") or not metadata.get("jwt_token"):
            raise GoodreadsClientError("Goodreads page did not expose the GraphQL metadata needed for tags.")
        return {
            "book_id": str(metadata["book_id"]),
            "jwt_token": str(metadata["jwt_token"]),
        }
