import test from "node:test";
import assert from "node:assert/strict";
import {
  sanitizeReleases,
  firmwareAsset,
  appAsset,
  GITHUB,
} from "./releases.mjs";
const tag = "v0.1.0-dev.21";
const asset = (name) => ({
  name,
  size: 1024,
  browser_download_url: `${GITHUB}/releases/download/${tag}/${name}`,
  digest: "sha256:" + "a".repeat(64),
});
const release = {
  tag_name: tag,
  published_at: "2026-10-28T00:00:00Z",
  prerelease: true,
  assets: [
    asset("NW-X1000-0.1.0-dev.21-firmware.zip"),
    asset("ebook-0.2.0-alpha.3.zip"),
  ],
};
test("accepts prereleases; excludes drafts, malformed responses and external download URLs", () => {
  const clean = sanitizeReleases([
    release,
    { ...release, draft: true },
    { ...release, tag_name: "../bad" },
    { ...release, tag_name: "v1.0.0", assets: [asset("x.zip")] },
  ]);
  assert.equal(clean.length, 2);
  assert.equal(clean[0].prerelease, true);
  assert.equal(clean[1].assets.length, 0);
  assert.throws(() => sanitizeReleases({ message: "rate limit" }));
});
test("firmware must match selected tag and missing packages stay unavailable", () => {
  const [clean] = sanitizeReleases([release]);
  assert.equal(firmwareAsset(clean, "firmware").name, release.assets[0].name);
  assert.equal(firmwareAsset(clean, "player-setup"), undefined);
  assert.equal(firmwareAsset(undefined, "firmware"), undefined);
});
test("app version comes from the published ZIP, not the current source version", () => {
  const [clean] = sanitizeReleases([release]);
  assert.equal(appAsset(clean, "ebook").version, "0.2.0-alpha.3");
  assert.equal(appAsset(clean, "book"), undefined);
  assert.equal(appAsset(clean, ".*"), undefined);
  assert.equal(
    appAsset(
      { ...clean, assets: [...clean.assets, asset("ebook-0.3.0.zip")] },
      "ebook",
    ),
    undefined,
  );
});
test("invalid digests and non-positive sizes never become checksums or downloads", () => {
  const [clean] = sanitizeReleases([
    {
      ...release,
      assets: [
        { ...asset("x.zip"), digest: "bad" },
        { ...asset("empty.zip"), size: 0 },
      ],
    },
  ]);
  assert.equal(clean.assets.length, 1);
  assert.equal(clean.assets[0].digest, null);
});
