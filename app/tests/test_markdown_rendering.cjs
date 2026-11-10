// Regressietests voor issue #46: markdown in bot-antwoorden moet opgemaakt
// worden (koppen, **vet**, lijsten); gebruikersinput, bronregel en foutmeldingen
// blijven platte tekst (nooit HTML).
const assert = require("node:assert/strict");

const { test } = require("node:test");

const { setup, runChat } = require("./chat_dom.cjs");

function chatWithAnswer(answer, question = "Vraag") {
  const env = setup("");
  env.context.fetch = (url) => {
    if (url === "/chat") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ answer, conversation_id: "conv-1" }),
      });
    }
    return new Promise(() => {});
  };
  runChat(env.context);
  env.elements.question.value = question;
  env.elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  return env;
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
}

function findAll(node, pred, out = []) {
  for (const child of node.children || []) {
    if (pred(child)) out.push(child);
    findAll(child, pred, out);
  }
  return out;
}

test("### in een bot-antwoord wordt een h3-kop, geen letterlijke hashes", async () => {
  const { elements } = chatWithAnswer("### Koptekst\n\nTekst");
  await flush();
  const bot = elements.messages.children[1];
  const h3 = findAll(bot, (n) => n.tagName === "H3");
  assert.equal(h3.length, 1);
  assert.equal(h3[0].textContent, "Koptekst");
  assert.ok(!bot.textContent.includes("###"), bot.textContent);
});

test("## en # worden koppen van het juiste niveau", async () => {
  const { elements } = chatWithAnswer("## Twee\n# Een");
  await flush();
  const bot = elements.messages.children[1];
  assert.equal(findAll(bot, (n) => n.tagName === "H2")[0].textContent, "Twee");
  assert.equal(findAll(bot, (n) => n.tagName === "H1")[0].textContent, "Een");
});

test("**vet** wordt een strong-element zonder asterisken", async () => {
  const { elements } = chatWithAnswer("Prefix **vet** suffix");
  await flush();
  const bot = elements.messages.children[1];
  const strong = findAll(bot, (n) => n.tagName === "STRONG");
  assert.equal(strong.length, 1);
  assert.equal(strong[0].textContent, "vet");
  const p = findAll(bot, (n) => n.tagName === "P")[0];
  assert.equal(p.textContent, "Prefix vet suffix");
  assert.ok(!bot.textContent.includes("**"), bot.textContent);
});

test("een lijst met - wordt een ul met li's", async () => {
  const { elements } = chatWithAnswer("- een\n- twee");
  await flush();
  const bot = elements.messages.children[1];
  const ul = findAll(bot, (n) => n.tagName === "UL");
  assert.equal(ul.length, 1);
  const items = findAll(ul[0], (n) => n.tagName === "LI");
  assert.deepEqual(items.map((n) => n.textContent), ["een", "twee"]);
});

test("de Bron-regel blijft een aparte span.bron in platte tekst", async () => {
  const { elements } = chatWithAnswer("Antwoord\nBron: Titel 20 (2026-09-21)");
  await flush();
  const bot = elements.messages.children[1];
  const bron = findAll(bot, (n) => n.className === "bron");
  assert.equal(bron.length, 1);
  assert.equal(bron[0].textContent, "Bron: Titel 20 (2026-09-21)");
  assert.equal(findAll(bot, (n) => n.tagName === "P")[0].textContent, "Antwoord");
});

test("HTML in een bot-antwoord wordt niet als element gerenderd", async () => {
  const { elements } = chatWithAnswer("<script>alert(1)</script>");
  await flush();
  const bot = elements.messages.children[1];
  assert.equal(findAll(bot, (n) => n.tagName === "SCRIPT").length, 0);
  assert.ok(bot.textContent.includes("<script>alert(1)</script>"));
});

test("eigen gebruikersbericht blijft ge-escaped platte tekst", async () => {
  const { elements } = chatWithAnswer("Antwoord", "<b>Hallo</b>");
  await flush();
  const user = elements.messages.children[0];
  assert.equal(user.children.length, 0);
  assert.equal(user.textContent, "<b>Hallo</b>");
});

test("foutmeldingen blijven platte tekst zonder koppen", async () => {
  const env = setup("");
  env.context.fetch = () => Promise.resolve({
    ok: false,
    json: () => Promise.resolve({ error: "Fout ###" }),
  });
  runChat(env.context);
  env.elements.question.value = "Vraag";
  env.elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
  await flush();
  const bot = env.elements.messages.children[1];
  assert.equal(bot.className, "msg error");
  assert.equal(bot.children.length, 0);
  assert.ok(bot.textContent.includes("Fout ###"));
});
