"""Browserlayout van de echte app-shell, zonder API- of Mistral-aanroepen."""

from base64 import b64encode
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import Browser, Page, expect


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


@pytest.mark.parametrize("width,height", [(360, 640), (390, 844), (430, 932), (844, 390), (1280, 720)])
def test_background_area_stays_between_collapsed_settings_and_composer(
    page: Page, shell_url: str, width: int, height: int
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(shell_url)
    page.locator("#taalniveau summary").click()
    privacy = page.locator("#privacy")
    messages = page.locator("#messages")
    footer = page.locator("footer")
    collapsed = messages.bounding_box()
    privacy_bounds = privacy.bounding_box()
    footer_bounds = footer.bounding_box()
    assert collapsed is not None and privacy_bounds is not None and footer_bounds is not None
    assert collapsed["y"] == pytest.approx(privacy_bounds["y"] + privacy_bounds["height"], abs=1)
    assert collapsed["y"] + collapsed["height"] == pytest.approx(footer_bounds["y"], abs=1)

    page.locator("#taalniveau summary").click()
    assert messages.bounding_box() == collapsed
    page.locator("#privacy summary").click()
    assert messages.bounding_box() == collapsed
    assert_composer_visible(page)


def test_portrait_background_fills_conversation_height_without_distortion(page: Page, shell_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(shell_url)
    background = page.locator("#messages").evaluate("""async node => {
        const style = getComputedStyle(node);
        const url = style.backgroundImage.match(/url\\(["']?(.*?)["']?\\)/);
        if (!url) return null;
        const image = new Image();
        image.src = url[1];
        await image.decode();
        return {
            url: image.src, width: image.naturalWidth, height: image.naturalHeight,
            size: style.backgroundSize, position: style.backgroundPosition,
            repeat: style.backgroundRepeat
        };
    }""")
    assert background is not None
    assert "Achtergrond%20A5" in background["url"]
    assert background["width"] < background["height"]
    assert background["size"] == "auto 100%"
    assert background["position"] == "50% 50%"
    assert background["repeat"] == "no-repeat"
    response = page.request.get(background["url"])
    assert response.ok
    assert len(response.body()) <= 200_000


@pytest.mark.parametrize("name", ["Achtergrond 16-9.jpg", "Achtergrond A5.png", "Achtergrond A5 liggend.png"])
def test_background_assets_are_reduced_proportionally(page: Page, name: str) -> None:
    asset = Path(__file__).resolve().parents[2] / "assets" / name
    image = b64encode(asset.read_bytes()).decode("ascii")
    dimensions = page.evaluate("""async encoded => {
        const image = new Image();
        image.src = "data:image/" + encoded.type + ";base64," + encoded.data;
        await image.decode();
        return [image.naturalWidth, image.naturalHeight];
    }""", {"type": "jpeg" if name.endswith(".jpg") else "png", "data": image})
    assert max(dimensions) <= 1280
    expected_ratio = {"Achtergrond 16-9.jpg": 941 / 1672, "Achtergrond A5.png": 1053 / 1494,
                      "Achtergrond A5 liggend.png": 1491 / 1055}[name]
    assert dimensions[0] / dimensions[1] == pytest.approx(expected_ratio, abs=0.002)


def test_background_is_available_when_the_webapp_starts_offline(browser: Browser, shell_url: str) -> None:
    context = browser.new_context(service_workers="allow")
    try:
        page = context.new_page()
        page.goto(shell_url)
        page.evaluate("navigator.serviceWorker.ready")
        page.reload()
        page.wait_for_function("navigator.serviceWorker.controller !== null")
        context.set_offline(True)
        page.goto(shell_url)
        assert page.locator("#messages").evaluate("""async node => {
            const url = getComputedStyle(node).backgroundImage.match(/url\\(["']?(.*?)["']?\\)/);
            if (!url) return false;
            const image = new Image();
            image.src = url[1];
            await image.decode();
            return image.naturalWidth > 0;
        }""")
    finally:
        context.close()


def test_composer_fits_visible_viewport_not_physical_screen(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    assert_composer_visible(page)


def test_composer_stays_visible_when_keyboard_opens_and_closes(page: Page, shell_url: str) -> None:
    open_shell(page, shell_url)
    before = page.locator("#messages").bounding_box()
    assert before is not None
    page.locator("#question").focus()
    page.evaluate("""
        () => {
            visualViewport.height = 448;
            visualViewport.dispatchEvent(new Event("resize"));
        }
    """)
    assert_composer_visible(page)
    keyboard = page.locator("#messages").bounding_box()
    assert keyboard is not None
    assert keyboard["y"] == pytest.approx(before["y"], abs=1)
    assert keyboard["height"] == pytest.approx(before["height"] - 349, abs=1)
    page.evaluate("""
        () => {
            visualViewport.height = 797;
            visualViewport.dispatchEvent(new Event("resize"));
        }
    """)
    assert_composer_visible(page)
    assert page.locator("#messages").bounding_box() == before


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
    box = page.locator("#messages").bounding_box()
    assert box is not None
    pixel = {"x": box["x"] + 2, "y": box["y"] + box["height"] / 2, "width": 1, "height": 1}
    page.locator("#messages").evaluate("node => { node.scrollTop = 0; }")
    background_before = page.screenshot(clip=pixel)
    page.locator("#messages").evaluate("node => { node.scrollTop = node.scrollHeight; }")
    assert page.screenshot(clip=pixel) == background_before
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


def test_both_settings_remain_accessible_when_contents_exceed_viewport(page: Page, shell_url: str) -> None:
    page.set_viewport_size({"width": 360, "height": 640})
    page.goto(shell_url)
    page.locator(".taalniveau-uitleg").evaluate("node => { node.textContent = node.textContent.repeat(20); }")
    page.locator("#privacy summary").click()
    expect(page.locator("#privacy details")).to_have_attribute("open", "")
    assert_composer_visible(page)
    page.locator("#privacy summary").click()
    page.locator("#taalniveau summary").click()
    assert_composer_visible(page)
