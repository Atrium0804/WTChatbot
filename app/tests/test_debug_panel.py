"""Browser checks for live trace rendering and visible polling failures."""

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, Route, expect

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tracing  # noqa: E402


def test_panel_updates_preserves_collapsed_traces_and_recovers_from_errors(page: Page):
    store = tracing.TraceStore(enabled=True)
    unavailable = False

    def serve(route: Route) -> None:
        if route.request.url.endswith("/debug/traces"):
            route.fulfill(
                status=503 if unavailable else 200,
                content_type="application/json",
                body=json.dumps({"traces": store.snapshot()}),
            )
        elif route.request.url.endswith("/debug"):
            route.fulfill(
                content_type="text/html",
                body=(Path(__file__).resolve().parent.parent / "debug.html").read_text(encoding="utf-8"),
            )
        else:
            route.abort()

    page.route("**/*", serve)
    page.goto("http://127.0.0.1:8769/debug")
    expect(page.locator("#status")).to_contain_text("Nog geen traces")
    trace = store.start("conversation")
    trace.record("route", route="bypass", reason="regex_lookup")
    trace.record("done")
    expect(page.locator("#traces summary")).to_contain_text("bypass | done")
    expect(page.locator("#traces pre")).to_contain_text("regex_lookup")
    page.locator("#traces summary").click()
    trace.record("done")
    expect(page.locator("#traces details")).not_to_have_attribute("open", "")
    unavailable = True
    expect(page.locator("#status.error")).to_contain_text("HTTP 503")
    unavailable = False
    expect(page.locator("#status")).to_have_class("")
    second = store.start("other-conversation")
    second.record("route", route="router")
    expect(page.locator("#traces details")).to_have_count(2)
    expect(page.locator("#traces details").first).to_have_attribute("open", "")
    expect(page.locator("#traces details").last).not_to_have_attribute("open", "")
