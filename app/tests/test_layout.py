"""Browserlayout van de echte app-shell, zonder API- of Mistral-aanroepen."""

from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object]) -> dict[str, object]:
    # Service workers omzeilen Playwright-routes; deze tests stubben alleen de API.
    return {**browser_context_args, "service_workers": "block"}


@pytest.fixture(scope="module")
def shell_url() -> Iterator[str]:
    static = Path(__file__).resolve().parent.parent / "static"
    handler = partial(SimpleHTTPRequestHandler, directory=str(static))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def open_shell(page: Page, url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 797})
    page.add_init_script("""
        Object.defineProperty(navigator, "standalone", {value: true});
        Object.defineProperty(screen, "width", {value: 390});
        Object.defineProperty(screen, "height", {value: 844});
        const viewport = new EventTarget();
        Object.assign(viewport, {
            width: 390, height: 797, offsetTop: 0, offsetLeft: 0, scale: 1
        });
        Object.defineProperty(window, "visualViewport", {value: viewport});
    """)
    page.goto(url)


def assert_composer_visible(page: Page) -> None:
    page.wait_for_function("""
        () => {
            const v = window.visualViewport;
            const top = v ? v.offsetTop : 0;
            const left = v ? v.offsetLeft : 0;
            const bottom = top + (v ? v.height : window.innerHeight);
            const right = left + (v ? v.width : window.innerWidth);
            return ["footer", "#question", "#send"].every(selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return r.height > 0 && r.width > 0 &&
                    r.top >= top - 1 && r.bottom <= bottom + 1 &&
                    r.left >= left - 1 && r.right <= right + 1;
            });
        }
    """, timeout=3000)


def test_composer_fits_visible_viewport_not_physical_screen(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    assert_composer_visible(page)


def test_composer_stays_visible_when_keyboard_opens_and_closes(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    page.locator("#question").focus()
    page.evaluate("""
        () => {
            visualViewport.height = 448;
            visualViewport.dispatchEvent(new Event("resize"));
        }
    """)
    assert_composer_visible(page)
    page.evaluate("""
        () => {
            visualViewport.height = 797;
            visualViewport.dispatchEvent(new Event("resize"));
        }
    """)
    assert_composer_visible(page)


def test_composer_follows_visible_viewport_offset_during_focus(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    page.evaluate("""
        () => {
            visualViewport.height = 448;
            visualViewport.dispatchEvent(new Event("resize"));
            visualViewport.offsetTop = -7;
            visualViewport.dispatchEvent(new Event("scroll"));
        }
    """)
    assert_composer_visible(page)


def test_diagnostics_distinguish_page_scroll_from_visible_viewport_offset(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url + "?debug=1")
    page.set_viewport_size({"width": 390, "height": 448})
    page.evaluate("""
        () => {
            Object.assign(visualViewport, {
                height: 448, offsetTop: 349, pageTop: 698, pageLeft: 0
            });
            visualViewport.dispatchEvent(new Event("resize"));
            window.scrollTo(0, 349);
            visualViewport.dispatchEvent(new Event("scroll"));
        }
    """)
    page.wait_for_function("""
        () => {
            const lines = document.querySelector("#chat-debug").textContent.split("\\n");
            const snapshots = lines.filter(line => line.startsWith("[DEBUG-54] {"));
            const snapshot = JSON.parse(snapshots.at(-1).slice("[DEBUG-54] ".length));
            return snapshot.scroll?.y === 349 && snapshot.scroll.x === 0 &&
                snapshot.viewport.top === 349 && snapshot.viewport.pageTop === 698 &&
                snapshot.viewport.pageLeft === 0 && snapshot.bodyTop === "349px" &&
                snapshot.body.top === 0 && snapshot.layout.width === 390 &&
                snapshot.layout.height === 448;
        }
    """, timeout=3000)


def test_composer_recovers_on_pageshow_without_a_resize_event(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    page.evaluate("""
        () => {
            visualViewport.height = 448;
            visualViewport.dispatchEvent(new Event("resize"));
        }
    """)
    assert_composer_visible(page)


    page.evaluate("""
        () => {
            visualViewport.height = 797;
            window.dispatchEvent(new Event("pageshow"));
        }
    """)
    page.wait_for_function("""
        () => Math.abs(document.querySelector("footer").getBoundingClientRect().bottom - 797) <= 1
    """, timeout=3000)
    assert_composer_visible(page)


def test_layout_resizes_across_phone_landscape_and_desktop(page: Page, shell_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 720})
    page.goto(shell_url)
    for width, height in [(1280, 720), (320, 640), (844, 390), (390, 797)]:
        page.set_viewport_size({"width": width, "height": height})
        assert_composer_visible(page)
        title = page.locator("header h1").bounding_box()
        assert title is not None
        assert title["y"] >= 0
        assert title["y"] + title["height"] <= height


def test_pinch_zoom_does_not_reflow_the_app(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    assert_composer_visible(page)
    before = page.locator("body").bounding_box()
    page.evaluate("""
        () => {
            Object.assign(visualViewport, {height: 398.5, offsetTop: 20, scale: 2});
            visualViewport.dispatchEvent(new Event("resize"));
            visualViewport.dispatchEvent(new Event("scroll"));
        }
    """)
    after = page.locator("body").bounding_box()
    assert before == after


def test_layout_works_without_visual_viewport(page: Page, shell_url: str) -> None:
    page.add_init_script('Object.defineProperty(window, "visualViewport", {value: undefined});')
    page.set_viewport_size({"width": 360, "height": 640})
    page.goto(shell_url)
    assert_composer_visible(page)
    page.set_viewport_size({"width": 844, "height": 390})
    assert_composer_visible(page)


def test_long_conversation_scrolls_without_moving_header_or_composer(page: Page, shell_url: str) -> None:
    page.route("**/chat", lambda route: route.fulfill(json={
        "conversation_id": "layout-test",
        "answer": "Dit is een lang testantwoord zonder echte gebruikersgegevens. " * 100,
    }))
    open_shell(page, shell_url)
    before = page.locator("header").bounding_box()
    page.locator("#question").fill("Hallo")
    page.locator("#question").press("Enter")
    expect(page.get_by_role("button", name="Goed antwoord")).to_be_visible()
    assert_composer_visible(page)
    state = page.locator("#messages").evaluate("""
        node => {
            const scrollable = node.scrollHeight > node.clientHeight;
            node.scrollTop = 0;
            const first = node.scrollTop;
            node.scrollTop = node.scrollHeight;
            return {scrollable, first, last: node.scrollTop, pageScroll: window.scrollY};
        }
    """)
    assert state["scrollable"]
    assert state["first"] == 0
    assert state["last"] > 0
    assert state["pageScroll"] == 0
    assert page.locator("header").bounding_box() == before
    assert_composer_visible(page)
