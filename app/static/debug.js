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
    panel.textContent = lines.slice(-30).join("\n");
  }

  function errorType(error) {
    var name = error && error.name;
    return /^(Error|TypeError|ReferenceError|SyntaxError|RangeError|SecurityError|QuotaExceededError)$/.test(name)
      ? name : "Error";
  }

  record("Diagnostiek actief (geen berichtinhoud)");
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
