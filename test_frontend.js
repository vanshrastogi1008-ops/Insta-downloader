// Minimal fake DOM to exercise app.js without a browser.
const assert = require("assert"), fs = require("fs");
const html = fs.readFileSync(__dirname + "/../static/index.html", "utf8");
for (const id of ["url", "paste", "go", "msg", "results"]) assert(html.includes(`id="${id}"`), "missing #" + id);

function el(tag) {
  const e = { tag, children: [], listeners: {}, className: "", textContent: "", value: "", disabled: false,
    classList: { add(c) { e.className += " " + c; }, remove() {} },
    addEventListener(t, f) { e.listeners[t] = f; },
    append(...c) { e.children.push(...c); }, appendChild(c) { e.children.push(c); },
    focus() {}, set innerHTML(v) { e.children = []; }, get innerHTML() { return ""; } };
  return e;
}
const ids = {}; for (const id of ["url", "paste", "go", "msg", "results"]) ids[id] = el("x");
global.document = { getElementById: (i) => ids[i], createElement: el };
Object.defineProperty(globalThis, "navigator", { value: { clipboard: { readText: async () => "  https://www.instagram.com/reel/AAA/  " } }, configurable: true });
global.setTimeout = () => 0;
let calls = [];
global.fetch = async (u, o) => { calls.push([u, o]);
  return { ok: true, json: async () => ({ url: "https://www.instagram.com/reel/AAA/", items: [
    { index: 1, title: "t", uploader: "u", duration: 65, thumbnail: "https://x.cdninstagram.com/a.jpg", video: true, audio: true, image: true },
    { index: 2, title: "p", thumbnail: "https://x.cdninstagram.com/b.jpg", video: false, audio: false, image: true }] }) }; };
require("../static/app.js");

(async () => {
  await ids.paste.listeners.click(); assert.strictEqual(ids.url.value, "https://www.instagram.com/reel/AAA/");
  await ids.go.listeners.click();
  assert.strictEqual(calls[0][0], "/api/info");
  assert.strictEqual(JSON.parse(calls[0][1].body).url, ids.url.value);
  assert.strictEqual(ids.results.children.length, 2);
  const links = (card) => card.children[1].children[2].children.map((a) => a.href);
  const l1 = links(ids.results.children[0]), l2 = links(ids.results.children[1]);
  assert.strictEqual(l1.length, 3); assert(l1[0].includes("kind=video&item=1")); assert(l1[1].includes("kind=audio"));
  assert(l1[2].startsWith("/api/image?src=https%3A%2F%2Fx.cdninstagram.com"));
  assert.strictEqual(l2.length, 1, "photo-only item must have only the photo button");
  assert.strictEqual(ids.go.disabled, false);
  // empty input shows error and does not call the API
  calls = []; ids.url.value = ""; await ids.go.listeners.click();
  assert.strictEqual(calls.length, 0); assert.strictEqual(ids.msg.className, "error");
  // server error is shown
  global.fetch = async () => ({ ok: false, json: async () => ({ error: "bad link" }) });
  ids.url.value = "x"; await ids.go.listeners.click();
  assert.strictEqual(ids.msg.textContent, "bad link");
  console.log("frontend tests ok");
})().catch((e) => { console.error(e); process.exit(1); });
