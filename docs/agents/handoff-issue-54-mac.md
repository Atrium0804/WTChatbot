# Issue #54: continue on the Mac

## Goal and current outcome

Continue [issue #54](https://github.com/Atrium0804/WTChatbot/issues/54), focusing on the **blurred heading in the installed iPhone PWA**.

The latest device screenshot confirms:
- The bottom blue strip is gone.
- The question field and Send button are fully visible.
- The heading remains visibly blurred; the subtitle is sharp.

The diagnostic `PASS` checks DOM bounds, not native overlays or text rendering. It does not prove that the blur is fixed.

The user has a Mac but last reported that **Safari Web Inspector was not connected yet**. The next step is remote inspection of the currently failing installed PWA.

## Continue from the handoff commit

- Repository: `Atrium0804/WTChatbot`.
- Branch: `54-ios-safe-area-insets`.
- Baseline before this handoff commit: `e7b2aff` (`chore: hernoem Wheely naar Wielie`).
- This document is committed alongside the viewport implementation, browser tests, diagnostics and status-bar trial.

The commit is local until explicitly pushed or transferred. Before continuing on the Mac, coordinate synchronization with the user and verify that the checkout includes the handoff commit, including the new viewport script and browser tests. A clone of the previously published branch is not sufficient.

The user handles deployment. Keep working on the same issue branch and preserve unrelated changes. Recreate the Python environment on the Mac rather than copying the Windows venv; transfer no secrets or environment files.

## Existing artifacts to read, not recreate

- [Coding principles](../../CODING_PRINCIPLES.md) and [contribution workflow](../../CONTRIBUTING.md).
- [Diagnostics procedure and status-bar trial](../how-to/toon-chatdiagnostiek-op-je-telefoon.md).
- [Browser tests and device-check limitations](../how-to/test-chatlayout.md).
- [App shell](../../app/static/index.html), [viewport fitter](../../app/static/viewport.js), [diagnostics](../../app/static/debug.js), and [service worker](../../app/static/sw.js): inspect the handoff commit for implementation details.
- [Real-browser regression coverage](../../app/tests/test_layout.py).
- [Shell/configuration tests](../../app/tests/test_app.py), [JavaScript diagnostic tests](../../app/tests/test_debug.cjs), and [DOM harness](../../app/tests/chat_dom.cjs).
- [Test dependencies](../../app/requirements-dev.txt) and [app setup](../../app/README.md).

The existing branding/icon work is already in earlier commits. Preserve the Wielie name and club colours.

## Controlled experiment and evidence

The user approved changing **only** the iOS status-bar setting from `black-translucent` to `default`, with the necessary shell cache bump. The viewport code was left unchanged for this trial.

Current configuration markers:
- `apple-mobile-web-app-status-bar-style`: `default`.
- Service-worker cache: `wtchat-shell-v16`.
- Diagnostic marker: `viewport-54-v3`.

Latest device measurements after the trial:
- Standalone/display-mode standalone: both true.
- Screen: 390 x 844 CSS pixels.
- Inner size, layout viewport and visual viewport: 390 x 797.
- Window scroll, visual viewport offsets and page offsets: all zero.
- Body bounds: top 0, bottom 797; computed height 797px; CSS top 0px.
- Header: top 0, bottom 55.1875.
- Footer: bottom 797; question and Send button: bottom 755.
- Safe-area padding probe: top 0px, right 0px, bottom 34px, left 0px.

Before the status-bar trial, the top safe-area value was 47px and the header ended at 102.1875; the title was also blurred. The new screenshot has no bottom strip but still has title blur. This is a partial improvement, not a proven full explanation.

The preceding Safari browser screenshot had a sharp heading and visible composer. The blue area containing Safari's address/navigation controls was browser UI, not missing application height. Keep browser-chrome space separate from application height.

The user previously reported iOS 27.0.1; verify device/software versions if relevant rather than assuming simulator behavior matches.

## Next investigation on the Mac

1. Establish Safari remote inspection using the [official WebKit instructions](https://webkit.org/web-inspector/enabling-web-inspector/). Select **the installed Wielie PWA on the iPhone**, not an ordinary Safari tab or a desktop/emulated page. Keep the failing deployed version installed for a baseline.
2. Observe the actual phone while inspecting. The remaining blur has not been reproduced in an unattended local test; the desktop Chromium/WebKit suites are not a native iPhone reproduction.
3. The pending proposed inspection is:

   ```js
   inspect(document.querySelector("header h1"))
   ```

   Then inspect the selected heading in Elements. If the context menu offers **Capture Screenshot**, capture it and compare the saved heading at normal size with the phone's blurred heading. Availability has not been verified on the user's Safari version.
4. A sharp inspector capture versus a blurred phone display would help locate the difference later in rendering/compositing/native UI. A blurred capture would motivate inspecting the web-rendering path. Neither result alone proves a particular cause.
5. If capture is unavailable, inspect computed styles on the heading and its ancestors, especially `filter`, standard/prefixed `backdrop-filter`, `text-shadow`, `transform`, opacity and font properties. Keep probes targeted and avoid collecting chat content, IDs, credentials, full HARs or unrelated data.
6. Establish a controlled red/green device check for the exact blur before another fix. Change one variable at a time and prefer measured causes over extra fixed padding or device-specific viewport corrections.

Apple's [archived meta-tag reference](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariHTMLRef/Articles/MetaTags.html) documents content below the status bar for `default`, versus behind it for `black-translucent`. This motivated the trial; the archived description is not proof of current-iOS compositor behavior.

## Validation before the handoff commit

- **63 app tests passed**, including **18 browser cases** across Chromium and WebKit.
- **31 JavaScript tests passed**.
- `git diff --check` passed.
- Those tests establish the covered web behavior/configuration, not native blur correctness.
- A pytest-playwright fixture deprecation warning was observed; it is not the app failure.

Use the existing test instructions. A corresponding focused macOS browser command, after documented dependency/browser setup, is:

```sh
.venv/bin/python -m pytest app/tests/test_layout.py -q --browser chromium --browser webkit
```

Report Mac test/device checks only after actually running them.

## Suggested skills

Call the Skill tool for:
- **`diagnosing-bugs`** first: continue the evidence/feedback-loop discipline and distinguish native-device findings from DOM-only tests.
- **`tdd`** when implementing a fix or adding regression coverage. Previously agreed seams were actual DOM/layout/scroll behavior, captured viewport-event replay, and physical-device verification. A blur regression needs to exercise the real rendering symptom.
- **`write-documentation`** if updating developer documentation.

Keep the temporary opt-in diagnostics until the original device symptom is genuinely fixed. Then perform the diagnosing-bugs cleanup, retain appropriate regression coverage, and document the verified cause.
