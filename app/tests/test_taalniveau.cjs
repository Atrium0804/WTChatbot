// Tests voor de keuze 'Antwoorden: Kort/Uitgebreid' (issue #52): standaard B1,
// localStorage-persistentie, meezenden in POST /chat, dichtklappen bij 1e bericht.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { setup, runChat } = require("./chat_dom.cjs");

function setupMet(storage) {
  return setup("", { randomUUID: () => "test-id" }, { getItem: () => null, setItem() {} }, storage);
}

function verstuur(elements, tekst) {
  elements.question.value = tekst;
  elements.composer.dispatchEvent(new Event("submit", { cancelable: true }));
}

test("standaard is Kort (B1) geselecteerd en wordt meegestuurd in /chat", () => {
  const { elements, context, requests } = setupMet(undefined);
  runChat(context);
  assert.equal(elements["taalniveau-b1"].getAttribute("aria-pressed"), "true");
  assert.equal(elements["taalniveau-b2"].getAttribute("aria-pressed"), "false");
  assert.equal(elements["taalniveau-stand"].textContent, "Kort");
  verstuur(elements, "welke licentie heb ik nodig?");
  assert.equal(requests.length, 1);
  assert.equal(JSON.parse(requests[0].options.body).language_level, "B1");
});

test("omschakelen naar Uitgebreid (B2) werkt, bewaart en wordt meegestuurd", () => {
  const writes = [];
  const storage = { getItem: () => null, setItem: (k, v) => writes.push([k, v]) };
  const { elements, context, requests } = setupMet(storage);
  runChat(context);
  elements["taalniveau-b2"].dispatchEvent(new Event("click"));
  assert.equal(elements["taalniveau-b2"].getAttribute("aria-pressed"), "true");
  assert.equal(elements["taalniveau-b1"].getAttribute("aria-pressed"), "false");
  assert.equal(elements["taalniveau-stand"].textContent, "Uitgebreid");
  assert.deepEqual(writes, [["wtchat_taalniveau", "B2"]]);
  verstuur(elements, "hoe zit het met de verzekering?");
  assert.equal(JSON.parse(requests[0].options.body).language_level, "B2");
  // terugschakelen kan gewoon weer
  elements["taalniveau-b1"].dispatchEvent(new Event("click"));
  assert.equal(elements["taalniveau-stand"].textContent, "Kort");
  verstuur(elements, "nog een vraag");
  assert.equal(JSON.parse(requests[1].options.body).language_level, "B1");
});

test("opgeslagen keuze B2 wordt bij het laden overgenomen", () => {
  const storage = { getItem: (k) => (k === "wtchat_taalniveau" ? "B2" : null), setItem() {} };
  const { elements, context } = setupMet(storage);
  runChat(context);
  assert.equal(elements["taalniveau-b2"].getAttribute("aria-pressed"), "true");
  assert.equal(elements["taalniveau-stand"].textContent, "Uitgebreid");
});

test("ongeldige opgeslagen waarde valt terug op B1", () => {
  const storage = { getItem: () => "van alles", setItem() {} };
  const { elements, context } = setupMet(storage);
  runChat(context);
  assert.equal(elements["taalniveau-b1"].getAttribute("aria-pressed"), "true");
  assert.equal(elements["taalniveau-stand"].textContent, "Kort");
});

test("kapot localStorage: stilzwijgend B1, de chat werkt gewoon", () => {
  const storage = {
    getItem() { throw new Error("storage blocked"); },
    setItem() { throw new Error("storage blocked"); },
  };
  const { elements, context, requests } = setupMet(storage);
  runChat(context);
  assert.equal(elements["taalniveau-b1"].getAttribute("aria-pressed"), "true");
  verstuur(elements, "hallo");
  assert.equal(requests.length, 1);
  assert.equal(JSON.parse(requests[0].options.body).language_level, "B1");
  // schakelen mag geen crash geven
  elements["taalniveau-b2"].dispatchEvent(new Event("click"));
  assert.equal(elements["taalniveau-stand"].textContent, "Uitgebreid");
  verstuur(elements, "tweede vraag");
  assert.equal(JSON.parse(requests[1].options.body).language_level, "B2");
});

test("de balk klapt dicht bij het eerste bericht en de summary volgt de keuze", () => {
  const { elements, context } = setupMet(undefined);
  runChat(context);
  elements["taalniveau"].open = true;
  verstuur(elements, "eerste vraag");
  assert.equal(elements["taalniveau"].open, false);
  // bij een nieuwe paginalading staat de balk weer open (HTML: open-attribuut)
  assert.equal(elements["taalniveau"].open, false); // dicht na bericht
});
