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
  localStorage,
  viewportFixture,
) {
  const document = new EventTarget();
  const window = new EventTarget();
  window.requestAnimationFrame = (callback) => callback();
  if (localStorage !== undefined) window.localStorage = localStorage;
  const elements = {};
  const requests = [];
  function element(tag) {
    const node = new EventTarget();
    let text = "";
    const attributes = {};
    Object.defineProperty(node, "textContent", {
      get() { return text + this.children.map((c) => c.textContent).join(""); },
      set(v) { text = String(v); this.children.length = 0; },
      configurable: true,
    });
    Object.assign(node, {
      tagName: (tag || "div").toUpperCase(),
      style: {}, value: "", children: [],
      setAttribute(name, value) { attributes[name] = String(value); },
      getAttribute(name) { return name in attributes ? attributes[name] : null; },
      focus() {},
      appendChild(child) { this.children.push(child); },
      requestSubmit() { this.dispatchEvent(new Event("submit", { cancelable: true })); },
    });
    return node;
  }
  for (const id of [
    "messages", "composer", "question", "send",
    "taalniveau", "taalniveau-stand", "taalniveau-b1", "taalniveau-b2",
  ]) {
    elements[id] = element();
  }
  document.body = element();
  document.createElement = (tag) => element(tag);
  document.createTextNode = (text) => {
    const node = element("#text");
    node.textContent = text;
    return node;
  };
  document.getElementById = (id) => elements[id];
  if (viewportFixture) {
    Object.assign(window, viewportFixture.window);
    document.documentElement = element();
    elements.header = element();
    elements.footer = element();
    document.querySelector = (tag) => elements[tag];
    for (const [id, rect] of Object.entries(viewportFixture.bounds)) {
      const node = id === "body" ? document.body : elements[id];
      node.getBoundingClientRect = () => rect;
    }
    const createElement = document.createElement;
    document.createElement = (tag) => {
      const node = createElement(tag);
      node.remove = () => {
        document.body.children.splice(document.body.children.indexOf(node), 1);
      };
      return node;
    };
  }
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
