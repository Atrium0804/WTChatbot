// Tests voor het pollen van /chat/status/<job> in de typing-bubble (issue #85).
// Draait het echte script uit index.html.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { setup, runChat } = require("./chat_dom.cjs");

const settle = () => new Promise((resolve) => setImmediate(resolve));

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) };
}

// Bouw een VM-context met fake timers die we handmatig kunnen afvuren.
function makeEnv(fetchImpl) {
  const env = setup("");
  const timers = [];
  env.context.setTimeout = (fn, ms) => { timers.push({ fn, ms, fired: false }); return timers.length; };
  env.context.clearTimeout = (id) => { if (timers[id - 1]) timers[id - 1].fired = true; };
  env.context.AbortController = class {
    constructor() { this.signal = { aborted: false }; }
    abort() { this.signal.aborted = true; }
  };
  env.context.fetch = fetchImpl;
  runChat(env.context);
  return {
    ...env,
    timers,
    fireTimers: (ms) => {
      for (const t of timers) {
        if (t.ms === ms && !t.fired) { t.fired = true; t.fn(); }
      }
    },
  };
}

function submitQuestion(env, text) {
  env.elements.question.value = text || "Vraag";
  env.elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
}

function lastMessage(env) {
  const messages = env.elements.messages.children;
  return messages[messages.length - 1];
}

test("202 + status done: poll toont fase en dan het antwoord", async () => {
  const fetchCalls = [];
  const env = makeEnv((url) => {
    fetchCalls.push(url);
    if (url === "/chat") {
      return Promise.resolve(jsonResponse(202, { job_id: "job-1", conversation_id: "c1" }));
    }
    if (url === "/chat/status/job-1") {
      // eerste poll: working, tweede poll: done
      const callCount = fetchCalls.filter((u) => u === "/chat/status/job-1").length;
      if (callCount === 1) {
        return Promise.resolve(jsonResponse(200, { status: "working", phase: "Wielie denkt na…" }));
      }
      return Promise.resolve(jsonResponse(200, { status: "done", answer: "Het antwoord!", conversation_id: "c1" }));
    }
    return Promise.reject(new Error("unknown url " + url));
  });
  submitQuestion(env, "vraag");
  await settle();
  // vuur de eerste poll-timer af (2000ms)
  env.fireTimers(2000);
  await settle();
  await settle();
  // typing-bubble toont de phase
  assert.equal(lastMessage(env).className, "msg bot typing");
  // vuur de tweede poll af
  env.fireTimers(2000);
  await settle();
  await settle();
  await settle();
  const last = lastMessage(env);
  assert.equal(last.className, "msg bot");
  assert.match(last.textContent, /Het antwoord!/);
});

test("202 + status error: toon de foutmelding", async () => {
  const env = makeEnv((url) => {
    if (url === "/chat") {
      return Promise.resolve(jsonResponse(202, { job_id: "job-2", conversation_id: "c2" }));
    }
    if (url === "/chat/status/job-2") {
      return Promise.resolve(jsonResponse(200, { status: "error", error: "Te veel vragen." }));
    }
    return Promise.reject(new Error("unknown"));
  });
  submitQuestion(env, "vraag");
  await settle();
  env.fireTimers(2000);
  await settle();
  await settle();
  await settle();
  const last = lastMessage(env);
  assert.equal(last.className, "msg error");
  assert.equal(last.textContent, "Te veel vragen.");
});

test("200 (stub-mode) werkt direct zonder poll", async () => {
  const fetchCalls = [];
  const env = makeEnv((url) => {
    fetchCalls.push(url);
    if (url === "/chat") {
      return Promise.resolve(jsonResponse(200, { answer: "Stub antwoord", conversation_id: "c3" }));
    }
    return Promise.reject(new Error("no status poll expected"));
  });
  submitQuestion(env, "vraag");
  await settle();
  await settle();
  assert.deepEqual(fetchCalls, ["/chat"]);
  const last = lastMessage(env);
  assert.equal(last.className, "msg bot");
  assert.match(last.textContent, /Stub antwoord/);
});

test("status-poll faalt: terugval op staged-tijdmeldingen (#84)", async () => {
  let pollCount = 0;
  const env = makeEnv((url) => {
    if (url === "/chat") {
      return Promise.resolve(jsonResponse(202, { job_id: "job-3", conversation_id: "c4" }));
    }
    if (url === "/chat/status/job-3") {
      pollCount++;
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    return Promise.reject(new Error("unknown"));
  });
  submitQuestion(env, "vraag");
  await settle();
  // poll faalt -> staged timer zou nog steeds werken
  env.fireTimers(2000); // poll timer (faalt)
  await settle();
  env.fireTimers(15000); // staged message timer
  assert.equal(lastMessage(env).textContent, "Ik zoek in de reglementen…");
});
