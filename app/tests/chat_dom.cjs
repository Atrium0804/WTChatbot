// Gedeelde harness voor de JavaScript-tests van de chat-UI: laadt de echte
// scripts uit app/static in een gesimuleerde DOM (node:vm + EventTarget).
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const debugSource = readFileSync(join(__dirname, "..", "static", "debug.js"), "utf8");
const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
const chatSource = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function setup(
  search,
  crypto = { randomUUID: () => "test-id" },
  sessionStorage = { getItem: () => null, setItem() {} },
) {
  const document = new EventTarget();
  const window = new EventTarget();
  const elements = {};
  const requests = [];
  function element() {
    const node = new EventTarget();
    Object.assign(node, {
      style: {}, value: "", children: [], textContent: "",
      setAttribute() {}, focus() {},
      appendChild(child) { this.children.push(child); },
      requestSubmit() { this.dispatchEvent(new Event("submit", { cancelable: true })); },
    });
    return node;
  }
  for (const id of ["messages", "composer", "question", "send"]) {
    elements[id] = element();
  }
  document.body = element();
  document.createElement = element;
  document.getElementById = (id) => elements[id];
  const context = vm.createContext({
    document, window, location: { search }, Event, crypto,
    sessionStorage,
    navigator: {}, console: { warn() {} },
    fetch: (url, options) => {
      requests.push({ url, options });
      return new Promise(() => {});
    },
  });
  vm.runInContext(debugSource, context);
  return { document, window, elements, context, requests };
}

function runChat(context) {
  vm.runInContext(chatSource, context);
}

module.exports = { setup, runChat, chatSource, debugSource };
