(function () {
  "use strict";
  if (!/(?:^\?|&)debug=1(?:&|$)/.test(location.search)) return;

  var panel = document.createElement("pre");
  panel.id = "chat-debug";
  panel.setAttribute("aria-label", "Chatdiagnostiek");
  panel.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:1000;" +
    "max-height:30vh;overflow:auto;margin:0;padding:8px;background:#fff;" +
    "color:#000;border:2px solid #033ec2;font:12px monospace;white-space:pre-wrap;";
  document.body.appendChild(panel);
  var lines = [];

  function record(text) {
    lines.push(text);
    if (lines.length > 30) lines.shift();
    panel.textContent = lines.join("\n");
  }

  function errorType(error) {
    var name = error && error.name;
    return /^(Error|TypeError|ReferenceError|SyntaxError|RangeError|SecurityError|QuotaExceededError)$/.test(name)
      ? name : "Error";
  }

  record("Diagnostiek actief (geen berichtinhoud)");
  function measureViewport(reason) {
    if (!window.getComputedStyle || !document.querySelector) {
      record("[DEBUG-54] viewportmeting niet beschikbaar");
      return;
    }
    var viewport = window.visualViewport;
    var top = viewport ? viewport.offsetTop : 0;
    var left = viewport ? viewport.offsetLeft : 0;
    var height = viewport ? viewport.height : window.innerHeight;
    var width = viewport ? viewport.width : window.innerWidth;
    var bottom = top + height;
    var right = left + width;
    function bounds(node) {
      var rect = node.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right };
    }
    function visible(rect) {
      return rect.top >= top - 1 && rect.bottom <= bottom + 1 &&
        rect.left >= left - 1 && rect.right <= right + 1;
    }
    var footer = document.querySelector("footer");
    var question = document.getElementById("question");
    var send = document.getElementById("send");
    var footerBounds = bounds(footer);
    var questionBounds = bounds(question);
    var sendBounds = bounds(send);
    var probe = document.createElement("div");
    probe.style.cssText = "position:fixed;visibility:hidden;pointer-events:none;" +
      "padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) " +
      "env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px);";
    document.body.appendChild(probe);
    var insets = window.getComputedStyle(probe);
    var safeArea = [insets.paddingTop, insets.paddingRight, insets.paddingBottom, insets.paddingLeft];
    probe.remove();
    var bodyStyle = window.getComputedStyle(document.body);
    record("[DEBUG-54] " + reason + " " +
      (visible(footerBounds) && visible(questionBounds) && visible(sendBounds) ? "PASS" : "FAIL") +
      " invoerbalk binnen visualViewport (native iOS-overlay niet meetbaar)");
    record("[DEBUG-54] " + JSON.stringify({
      version: "viewport-54-v3",
      standalone: navigator.standalone === true,
      displayStandalone: window.matchMedia("(display-mode: standalone)").matches,
      screen: [window.screen.width, window.screen.height],
      inner: [window.innerWidth, window.innerHeight],
      layout: { width: document.documentElement.clientWidth, height: document.documentElement.clientHeight },
      scroll: { x: window.scrollX, y: window.scrollY },
      viewport: {
        top: top, left: left, width: width, height: height, scale: viewport ? viewport.scale : 1,
        pageTop: viewport ? viewport.pageTop : window.scrollY,
        pageLeft: viewport ? viewport.pageLeft : window.scrollX
      },
      body: bounds(document.body),
      bodyHeight: bodyStyle.height,
      bodyTop: bodyStyle.top,
      appHeight: window.getComputedStyle(document.documentElement).getPropertyValue("--viewport-height"),
      header: bounds(document.querySelector("header")),
      footer: footerBounds,
      question: questionBounds,
      send: sendBounds,
      safeArea: safeArea,
      focus: document.activeElement === question ? "question" : document.activeElement === send ? "send" : "other"
    }));
  }
  function measureAfterLayout(reason) {
    window.requestAnimationFrame(function () { measureViewport(reason); });
  }
  measureAfterLayout("load");
  document.addEventListener("chat:viewport-fitted", function () { measureAfterLayout("viewport-fitted"); });
  document.addEventListener("chat:ready", function () { measureAfterLayout("chat-ready"); });
  ["resize", "pageshow", "orientationchange"].forEach(function (name) {
    window.addEventListener(name, function () { measureAfterLayout(name); });
  });
  if (window.visualViewport) {
    ["resize", "scroll"].forEach(function (name) {
      window.visualViewport.addEventListener(name, function () { measureAfterLayout("visualViewport-" + name); });
    });
  }
  panel.addEventListener("click", function () { measureAfterLayout("manual"); });
  ["init-start", "init-failed", "ready", "submit", "messages-rendered"].forEach(function (phase) {
    document.addEventListener("chat:" + phase, function () { record(phase); });
  });
  document.addEventListener("click", function (event) {
    if (event.target.id === "send") record("Verstuur aangeklikt");
  }, true);
  document.addEventListener("submit", function (event) {
    if (event.target.id === "composer") record("Formulier-submit ontvangen");
  }, true);
  window.addEventListener("error", function (event) {
    record("JavaScript: " + errorType(event.error) +
      " (regel " + (event.lineno || 0) + ", kolom " + (event.colno || 0) + ")");
  });
  window.addEventListener("unhandledrejection", function (event) {
    record("Promise: " + errorType(event.reason));
  });
  document.addEventListener("securitypolicyviolation", function () {
    record("Content-Security-Policy blokkeert een onderdeel; inspecteer de browserconsole");
  });
})();
