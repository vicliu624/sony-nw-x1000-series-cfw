// Executes the production JS in a synthetic DOM. This is not visual/browser QA.
import { JSDOM, VirtualConsole } from "jsdom";
import { readFile, readdir } from "node:fs/promises";
import assert from "node:assert/strict";
const output = new URL("../../dist/website/", import.meta.url);
const catalog = JSON.parse(
  await readFile(new URL("data/catalog.json", output), "utf8"),
);
const snapshot = JSON.parse(
  await readFile(new URL("data/releases.json", output), "utf8"),
);
const sdk = JSON.parse(
  await readFile(new URL("data/sdk.json", output), "utf8"),
);
const js = (await readdir(new URL("assets/", output))).find((n) =>
  /^index-.*\.js$/.test(n),
);
const code = await readFile(new URL(`assets/${js}`, output), "utf8");
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (e) => errors.push(e));
const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"></div></body></html>',
  {
    url: "https://vicliu624.github.io/sony-nw-x1000-series-cfw/?lang=zh-CN",
    runScripts: "outside-only",
    pretendToBeVisual: true,
    virtualConsole,
  },
);
const { window: w } = dom;
w.scrollTo = () => {};
w.matchMedia = () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
});
w.fetch = async (url) => ({
  ok: true,
  json: async () =>
    String(url).includes("api.github.com")
      ? snapshot.releases
      : String(url).includes("catalog.json")
        ? catalog
        : String(url).includes("sdk.json")
          ? sdk
          : snapshot,
});
w.eval(code);
const tick = () => new Promise((resolve) => setTimeout(resolve, 50));
const button = (text) =>
  [...w.document.querySelectorAll("button")].find(
    (el) => el.textContent.trim() === text,
  );
const click = async (element) => {
  assert.ok(element, "Expected UI element");
  element.click();
  await tick();
};
const route = async (value) => {
  w.location.hash = value;
  await tick();
};
const choose = async (label, option) => {
  const field = w.document.querySelector(
    `[role="combobox"][aria-labelledby="${label}"]`,
  );
  await click(field);
  await click(
    [...w.document.querySelectorAll('[role="option"]')].find((el) =>
      el.textContent.includes(option),
    ),
  );
};
try {
  await tick();
  await tick();
  assert.match(w.document.querySelector("h1").textContent, /你的 Walkman/);
  assert.equal(catalog.apps.length, 14);
  await click(button("EN"));
  assert.equal(w.document.documentElement.lang, "en");
  assert.match(w.document.querySelector("h1").textContent, /Your Walkman/);
  assert.equal(w.localStorage.getItem("x1000-language"), "en");
  await route("apps");
  assert.equal(w.document.querySelectorAll(".app-card").length, 14);
  await click(button("Music & radio"));
  assert.equal(w.document.querySelectorAll(".app-card").length, 2);
  await click(button("All apps"));
  const input = w.document.querySelector(
    'input[type="text"],input:not([type])',
  );
  Object.getOwnPropertyDescriptor(
    w.HTMLInputElement.prototype,
    "value",
  ).set.call(input, "QQ");
  input.dispatchEvent(new w.Event("input", { bubbles: true }));
  await tick();
  assert.equal(w.document.querySelectorAll(".app-card").length, 1);
  await click(w.document.querySelector(".app-card button"));
  assert.notEqual(
    w.document.querySelector('[role="dialog"]').getAttribute("aria-hidden"),
    "true",
  );
  assert.ok(
    w.document
      .querySelector(".app-detail .download-link")
      .href.includes("/qqmusic-"),
  );
  await click(button("Close details"));
  await route("firmware");
  assert.equal(
    w.document.querySelectorAll(".download-grid .download-link").length,
    0,
  );
  await choose("model-label", "NW-X1060");
  await click(w.document.querySelector('input[type="checkbox"]'));
  assert.equal(
    w.document.querySelectorAll(".download-grid .download-link").length,
    2,
  );
  for (const a of w.document.querySelectorAll(".download-grid .download-link"))
    assert.ok(a.href.includes("/v0.1.0-dev.21/"));
  await choose("model-label", "Another model");
  assert.equal(
    w.document.querySelectorAll(".download-grid .download-link").length,
    0,
  );
  assert.match(
    w.document.querySelector('[role="alert"]').textContent,
    /Do not install/,
  );
  await route("guide");
  assert.equal(w.document.querySelectorAll(".guide-card").length, 3);
  await route("developer");
  await tick();
  assert.match(w.document.querySelector("h1").textContent, /Hello, developer/);
  assert.equal(
    w.document.querySelectorAll(".developer-page .guide-card").length,
    3,
  );
  assert.equal(w.document.querySelectorAll(".sdk-preview-row img").length, 2);
  assert.match(
    w.document.querySelector(".developer-page .risk-box").textContent,
    /fails closed/,
  );
  if (sdk.release)
    assert.equal(
      w.document.querySelector(".sdk-actions .download-link").href,
      sdk.release.asset.url,
    );
  await click(button("中文"));
  assert.match(w.document.querySelector("h1").textContent, /你好，开发者/);
  assert.equal(w.document.documentElement.lang, "zh-CN");
  assert.equal(errors.length, 0, errors.map((e) => e.message).join("\n"));
  console.log(
    "Production DOM checks passed: bilingual navigation, 14 apps, category/search, app details, real downloads, model/risk gating and guides. Visual layout remains unverified.",
  );
} finally {
  dom.window.close();
}
