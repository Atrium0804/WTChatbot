// Regressietests voor issue #37: Enter in het vraagveld moet de vraag versturen
// via hetzelfde submit-pad als de knop "Verstuur"; Shift+Enter = nieuwe regel.
const assert = require("node:assert/strict");

const { test } = require("node:test");

const { setup, runChat } = require("./chat_dom.cjs");

function pressEnter(elements, overrides = {}) {
  const ev = new Event("keydown", { cancelable: true });
  Object.assign(ev, { key: "Enter", shiftKey: false, isComposing: false, ...overrides });
  elements.question.dispatchEvent(ev);
  return ev;
}

test("Enter verstuurt een niet-lege vraag via het formulier", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "Hallo Wheely";
  const ev = pressEnter(elements);
  assert.equal(ev.defaultPrevented, true, "Enter mag geen nieuwe regel invoegen");
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/chat");
  assert.equal(JSON.parse(requests[0].options.body).message, "Hallo Wheely");
  assert.equal(elements.question.value, "");
  assert.equal(elements.send.disabled, true);
});

test("Shift+Enter verstuurt niets en laat de nieuwe regel toe", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "Hallo";
  const ev = pressEnter(elements, { shiftKey: true });
  assert.equal(ev.defaultPrevented, false);
  assert.equal(requests.length, 0);
});

test("Enter tijdens IME-compositie verstuurt niets", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "Hallo";
  const ev = pressEnter(elements, { isComposing: true });
  assert.equal(ev.defaultPrevented, false);
  assert.equal(requests.length, 0);
});

test("Enter met een lege vraag verstuurt niets", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "   ";
  pressEnter(elements);
  assert.equal(requests.length, 0);
});

test("Enter terwijl een verzoek loopt verstuurt geen tweede verzoek", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "Eerste vraag";
  pressEnter(elements);
  assert.equal(requests.length, 1);
  assert.equal(elements.send.disabled, true);
  elements.question.value = "Tweede vraag";
  pressEnter(elements);
  assert.equal(requests.length, 1, "geen verzending zolang de send-knop disabled is");
});

test("de Verstuur-knop (formulier-submit) blijft werken", () => {
  const { elements, context, requests } = setup("");
  runChat(context);
  elements.question.value = "Via de knop";
  const submit = new Event("submit", { cancelable: true });
  elements.composer.dispatchEvent(submit);
  assert.equal(submit.defaultPrevented, true);
  assert.equal(requests.length, 1);
  assert.equal(JSON.parse(requests[0].options.body).message, "Via de knop");
});
