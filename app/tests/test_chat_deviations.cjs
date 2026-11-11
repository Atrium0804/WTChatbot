// Afwijkingen D1-D3 van het pariteitscontract (#54): foutmelding, feedback opnieuw
// proberen en focus na een antwoord. Draait het echte script uit index.html.
const assert = require("node:assert/strict");

const { test } = require("node:test");

const { setup, runChat } = require("./chat_dom.cjs");

const FALLBACK = "Er ging iets mis. Probeer het opnieuw.";

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) };
}

function htmlResponse(status) {
  return {
    ok: false,
    status,
    json: () => Promise.reject(new SyntaxError("Unexpected token '<', \"<html>\" is not valid JSON")),
  };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

async function ask(fetchImpl, { finePointer } = {}) {
  const env = setup("");
  env.context.fetch = fetchImpl;
  if (finePointer !== undefined) {
    env.window.matchMedia = (query) => ({ matches: query === "(pointer: fine)" && finePointer });
  }
  let focusCalls = 0;
  env.elements.question.focus = () => { focusCalls += 1; };
  runChat(env.context);
  focusCalls = 0;
  env.elements.question.value = "Vraag";
  env.elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  await settle();
  await settle();
  const messages = env.elements.messages.children;
  return { ...env, last: messages[messages.length - 1], focusCalls: () => focusCalls };
}

test("foutmelding van de server wordt getoond", async () => {
  const { last } = await ask(() => Promise.resolve(jsonResponse(429, { error: "Even rustig aan." })));
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, "Even rustig aan.");
});

test("een HTML-foutpagina geeft de Nederlandse standaardmelding", async () => {
  const { last } = await ask(() => Promise.resolve(htmlResponse(502)));
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, FALLBACK);
});

test("een netwerkfout geeft de Nederlandse standaardmelding", async () => {
  const { last } = await ask(() => Promise.reject(new TypeError("Failed to fetch")));
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, FALLBACK);
});

const answer = () => Promise.resolve(jsonResponse(200, { answer: "Antwoord", conversation_id: "c1" }));

test("na een antwoord krijgt het vraagveld focus bij een muis of trackpad", async () => {
  const { focusCalls } = await ask(answer, { finePointer: true });
  assert.equal(focusCalls(), 1);
});

test("na een antwoord blijft het toetsenbord dicht op een touchscreen", async () => {
  const { focusCalls } = await ask(answer, { finePointer: false });
  assert.equal(focusCalls(), 0);
});

test("bij het laden krijgt het vraagveld alleen focus bij een muis of trackpad", () => {
  for (const finePointer of [true, false]) {
    const { window, elements, context } = setup("");
    window.matchMedia = (query) => ({ matches: query === "(pointer: fine)" && finePointer });
    let focusCalls = 0;
    elements.question.focus = () => { focusCalls += 1; };
    runChat(context);
    assert.equal(focusCalls, finePointer ? 1 : 0, `finePointer=${finePointer}`);
  }
});

function click(node) {
  if (node.onclick) node.onclick();
  else node.dispatchEvent(new Event("click"));
}

async function answeredWithFeedback(feedbackResults) {
  const feedbackRequests = [];
  const env = await ask((url, options) => {
    if (url === "/chat") return answer();
    feedbackRequests.push(JSON.parse(options.body));
    const next = feedbackResults.shift();
    return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
  });
  const row = env.last.children.find((child) => child.className === "feedback");
  return { row, feedbackRequests };
}

test("mislukte feedback meldt dat en laat opnieuw proberen toe", async () => {
  const { row, feedbackRequests } = await answeredWithFeedback([
    new TypeError("Failed to fetch"),
    jsonResponse(200, { ok: true }),
  ]);
  const goed = row.children[0];
  click(goed);
  await settle();
  assert.match(row.textContent, /Feedback niet verstuurd\. Probeer het opnieuw\./);
  assert.doesNotMatch(row.textContent, /Bedankt/);
  click(goed);
  await settle();
  assert.equal(feedbackRequests.length, 2);
  assert.deepEqual(feedbackRequests[1], { conversation_id: "c1", rating: "positive", text: "" });
  assert.equal(row.textContent, "Bedankt voor je feedback.");
});

test("een HTTP-fout bij feedback telt als mislukt", async () => {
  const { row } = await answeredWithFeedback([jsonResponse(500, { error: "kapot" })]);
  click(row.children[0]);
  await settle();
  assert.match(row.textContent, /Feedback niet verstuurd\. Probeer het opnieuw\./);
});

test("negatieve feedback met toelichting kan na een fout opnieuw worden verstuurd", async () => {
  const { row, feedbackRequests } = await answeredWithFeedback([
    jsonResponse(503, {}),
    jsonResponse(200, { ok: true }),
  ]);
  const extra = row.children[2];
  const [textarea, verstuur] = extra.children;
  textarea.value = "Klopt niet";
  click(verstuur);
  await settle();
  click(verstuur);
  await settle();
  assert.deepEqual(feedbackRequests, [
    { conversation_id: "c1", rating: "negative", text: "Klopt niet" },
    { conversation_id: "c1", rating: "negative", text: "Klopt niet" },
  ]);
  assert.equal(row.textContent, "Bedankt voor je feedback.");
});
