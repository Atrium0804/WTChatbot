const assert = require("node:assert/strict");

const { test } = require("node:test");

const { setup, runChat } = require("./chat_dom.cjs");


test("diagnostics are opt-in with an exact query parameter", () => {
  for (const search of ["", "?debug=0", "?debug=10", "?other=debug=1"]) {
    assert.equal(setup(search).document.body.children.length, 0);
  }
  assert.equal(setup("?other=1&debug=1").document.body.children.length, 1);
});

test("real chat initialization and submission report milestones without content", () => {
  const { document, elements, context } = setup("?debug=1");
  runChat(context);
  elements.question.value = "PRIVATE TEST CONTENT";
  elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  const output = document.body.children[0].textContent;
  for (const phase of ["init-start", "ready", "submit", "messages-rendered"]) {
    assert.ok(output.split("\n").includes(phase), output);
  }
  assert.equal(elements.question.value, "");
  assert.equal(elements.send.disabled, true);
  assert.equal(elements.messages.children.length, 2);
  assert.ok(!output.includes("PRIVATE TEST CONTENT"));
  assert.ok(!output.includes("test-id"));
});

test("normal chat submission still works with diagnostics disabled", () => {
  const { document, elements, context } = setup("");
  runChat(context);
  elements.question.value = "Hello";
  const submit = new Event("submit", { cancelable: true });
  elements.composer.dispatchEvent(submit);
  assert.equal(submit.defaultPrevented, true);
  assert.equal(document.body.children.length, 0);
  assert.equal(elements.question.value, "");
  assert.equal(elements.send.disabled, true);
  assert.equal(elements.messages.children[0].textContent, "Hello");
});

test("diagnostic output is bounded and does not include form content", () => {
  const { document } = setup("?debug=1");
  for (let i = 0; i < 40; i++) {
    const click = new Event("click");
    Object.defineProperty(click, "target", {
      value: { id: "send", value: "PRIVATE CONTENT" },
    });
    document.dispatchEvent(click);
  }
  const submit = new Event("submit");
  Object.defineProperty(submit, "target", { value: { id: "composer" } });
  document.dispatchEvent(submit);
  const output = document.body.children[0].textContent;
  assert.equal(output.split("\n").length, 30);
  assert.ok(output.includes("Verstuur aangeklikt"));
  assert.ok(output.includes("Formulier-submit ontvangen"));
  assert.ok(!output.includes("PRIVATE CONTENT"));
});

test("chat works without randomUUID using a secure version-4 UUID", () => {
  const { document, elements, context, requests } = setup("?debug=1", {
    getRandomValues(bytes) { bytes.fill(255); return bytes; },
  });
  runChat(context);
  assert.ok(document.body.children[0].textContent.split("\n").includes("ready"));
  elements.question.value = "Hello";
  elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  assert.equal(elements.messages.children.length, 2);
  assert.equal(JSON.parse(requests[0].options.body).client_id,
    "ffffffff-ffff-4fff-bfff-ffffffffffff");
});

test("blocked session storage keeps the same generated ID for subsequent messages", () => {
  let generated = 0;
  const { elements, context, requests } = setup("", {
    randomUUID() { generated++; return "secure-test-id"; },
  }, {
    getItem() { throw new Error("storage blocked"); },
    setItem() { throw new Error("storage blocked"); },
  });
  runChat(context);
  for (let i = 0; i < 2; i++) {
    elements.question.value = "Hello";
    elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  }
  assert.equal(generated, 1);
  assert.deepEqual(requests.map((request) => JSON.parse(request.options.body).client_id),
    ["secure-test-id", "secure-test-id"]);
});

test("existing stored client ID is reused without generating another", () => {
  const { context, elements, requests } = setup("", {}, {
    getItem: () => "existing-client",
    setItem() { assert.fail("Existing ID should not be overwritten"); },
  });
  runChat(context);
  elements.question.value = "Hello";
  elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  assert.equal(JSON.parse(requests[0].options.body).client_id, "existing-client");
});

test("storage write failure does not generate an extra ID", () => {
  let generated = 0;
  const { context } = setup("", {
    randomUUID() { generated++; return "secure-test-id"; },
  }, {
    getItem: () => null,
    setItem() { throw new Error("storage full"); },
  });
  runChat(context);
  assert.equal(generated, 1);
});

test("unavailable or failing secure randomness shows an error and prevents native submission", () => {
  for (const crypto of [{}, null, { randomUUID() { throw new Error("unavailable"); } }]) {
    const { document, elements, context, requests } = setup("?debug=1", crypto);
    if (crypto === null) delete context.crypto;
    runChat(context);
    const submit = new Event("submit", { cancelable: true });
    elements.composer.dispatchEvent(submit);
    assert.equal(submit.defaultPrevented, true);
    assert.equal(elements.send.disabled, true);
    assert.equal(elements.question.disabled, true);
    assert.equal(elements.messages.children[0].className, "msg error");
    assert.match(elements.messages.children[0].textContent, /Chat kon niet starten/);
    assert.equal(requests.length, 0);
    assert.ok(document.body.children[0].textContent.split("\n").includes("init-failed"));
    assert.ok(!document.body.children[0].textContent.split("\n").includes("ready"));
  }
});

test("JavaScript errors and promise failures report types without private contents", () => {
  const { document, window } = setup("?debug=1", {});
  const error = new Event("error");
  Object.assign(error, {
    error: new TypeError("PRIVATE ERROR CONTENT"), lineno: 42, colno: 7,
  });
  window.dispatchEvent(error);
  const rejection = new Event("unhandledrejection");
  rejection.reason = { name: "PRIVATE ERROR CONTENT" };
  window.dispatchEvent(rejection);
  const output = document.body.children[0].textContent;
  assert.ok(output.includes("TypeError (regel 42, kolom 7)"));
  assert.ok(output.includes("Promise: Error"));
  assert.ok(!output.includes("PRIVATE ERROR CONTENT"));
});
