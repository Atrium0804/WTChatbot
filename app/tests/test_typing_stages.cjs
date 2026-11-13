// Tests voor de voortgangsindicatie in de typing-bubble en de client-timeout
// met retry (issue #84). Draait het echte script uit index.html.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { setup, runChat } = require("./chat_dom.cjs");

const settle = () => new Promise((resolve) => setImmediate(resolve));

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) };
}

// Bouw een VM-context met fake timers (setTimeout/clearTimeout) en een
// AbortController die we handmatig kunnen triggeren.
function makeEnv(fetchImpl) {
  const env = setup("");
  // Fake timers: we slaan callbacks op in plaats van echte timers te zetten.
  const timers = [];
  env.context.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  env.context.clearTimeout = (id) => { if (timers[id - 1]) timers[id - 1].fired = true; };
  // AbortController die we handmatig kunnen aborten
  let abortFn = null;
  env.context.AbortController = class {
    constructor() { this.signal = { aborted: false }; abortFn = () => { this.signal.aborted = true; this._abortCb && this._abortCb(); }; }
    abort() { this.signal.aborted = true; this._abortCb && this._abortCb(); }
    set onabort(cb) { this._abortCb = cb; }
  };
  env.context.fetch = fetchImpl;
  runChat(env.context);
  return { ...env, timers, fireAbort: () => abortFn && abortFn(), fireTimer: (ms) => {
    const t = timers.find((t) => t.ms === ms && !t.fired);
    if (t) { t.fired = true; t.fn(); }
  } };
}

function submitQuestion(env, text) {
  env.elements.question.value = text || "Vraag";
  env.elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
}

function lastMessage(env) {
  const messages = env.elements.messages.children;
  return messages[messages.length - 1];
}

test("typing-bubble start direct met 'Wielie denkt na…'", () => {
  const env = makeEnv(() => new Promise(() => {}));
  submitQuestion(env);
  const typing = lastMessage(env);
  assert.equal(typing.className, "msg bot typing");
  assert.equal(typing.textContent, "Wielie denkt na…");
});

test("na 15s-timer wisselt de typing-bubble naar 'Ik zoek in de reglementen…'", () => {
  const env = makeEnv(() => new Promise(() => {}));
  submitQuestion(env);
  env.fireTimer(15000);
  assert.equal(lastMessage(env).textContent, "Ik zoek in de reglementen…");
});

test("na 45s-timer wisselt de typing-bubble naar 'Dit duurt langer dan normaal…'", () => {
  const env = makeEnv(() => new Promise(() => {}));
  submitQuestion(env);
  env.fireTimer(15000);
  env.fireTimer(45000);
  assert.equal(lastMessage(env).textContent, "Dit duurt langer dan normaal, nog even geduld…");
});

test("bij abort na timeout verschijnt 'Dit duurt ongewoon lang'", async () => {
  let signalRef = null;
  const env = makeEnv((url, options) => {
    signalRef = options.signal;
    return new Promise((resolve, reject) => {
      signalRef._reject = reject;
    });
  });
  submitQuestion(env, "trage vraag");
  // simuleer de 120s timeout: abort het signaal -> fetch reject met AbortError
  const abortErr = new Error("The operation was aborted");
  abortErr.name = "AbortError";
  signalRef._reject(abortErr);
  await settle();
  await settle();
  const last = lastMessage(env);
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, "Dit duurt ongewoon lang — probeer het opnieuw.");
});

test("netwerkfout wordt één keer automatisch gereetryd", async () => {
  let calls = 0;
  const env = makeEnv(() => {
    calls++;
    if (calls === 1) return Promise.reject(new TypeError("Failed to fetch"));
    return Promise.resolve(jsonResponse(200, { answer: "Antwoord na retry", conversation_id: "c2" }));
  });
  submitQuestion(env, "vraag");
  await settle();
  await settle();
  await settle();
  await settle();
  assert.equal(calls, 2);
  const last = lastMessage(env);
  assert.equal(last.className, "msg bot");
  assert.match(last.textContent, /Antwoord na retry/);
});

test("na een abort wordt NIET automatisch gereetryd", async () => {
  let calls = 0;
  let signalRef = null;
  const env = makeEnv((url, options) => {
    calls++;
    signalRef = options.signal;
    return new Promise((resolve, reject) => {
      signalRef._reject = reject;
    });
  });
  submitQuestion(env, "vraag");
  // abort -> AbortError, geen retry
  const abortErr = new Error("The operation was aborted");
  abortErr.name = "AbortError";
  signalRef._reject(abortErr);
  await settle();
  await settle();
  await settle();
  assert.equal(calls, 1);
  const last = lastMessage(env);
  assert.equal(last.className, "msg error");
  assert.match(last.textContent, /ongewoon lang/);
});

test("server-foutmelding (HTTP error) wordt getoond zonder retry", async () => {
  let calls = 0;
  const env = makeEnv(() => {
    calls++;
    return Promise.resolve(jsonResponse(429, { error: "Te veel vragen." }));
  });
  submitQuestion(env, "vraag");
  await settle();
  await settle();
  assert.equal(calls, 1);
  const last = lastMessage(env);
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, "Te veel vragen.");
});

test("succesvol antwoord wist de typing-timers en toont het antwoord", async () => {
  const env = makeEnv(() => Promise.resolve(jsonResponse(200, { answer: "Klaar!", conversation_id: "c1" })));
  submitQuestion(env, "vraag");
  await settle();
  await settle();
  const last = lastMessage(env);
  assert.equal(last.className, "msg bot");
  assert.match(last.textContent, /Klaar!/);
  // de 15s/45s timers zijn gewist: afvuren heeft geen effect meer
  env.fireTimer(15000);
  assert.match(last.textContent, /Klaar!/);
});
