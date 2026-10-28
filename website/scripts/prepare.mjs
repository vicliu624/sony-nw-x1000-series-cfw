import { readFile, mkdir, writeFile, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = fileURLToPath(new URL("../../", import.meta.url));
const output = path.join(root, "website/public");
const policy = JSON.parse(
  await readFile(path.join(root, "config/release.json"), "utf8"),
);
await mkdir(path.join(output, "media/apps"), { recursive: true });
await mkdir(path.join(output, "data"), { recursive: true });
const apps = [];
for (const id of policy.apps) {
  const folder = path.join(root, "runtime/apps", id);
  const info = JSON.parse(
    await readFile(path.join(folder, "app.json"), "utf8"),
  );
  if (info.id !== id || info.target !== "sony-nw-x1000-jp")
    throw new Error(`Unexpected app: ${id}`);
  const version = (await readFile(path.join(folder, "VERSION"), "utf8")).trim();
  apps.push({
    id,
    title: info.title,
    summary: info.summary,
    description: info.description,
    changes: info.changes,
    version,
    channel: info.channel,
  });
  await copyFile(
    path.join(folder, "assets/icon.svg"),
    path.join(output, "media/apps", `${id}.svg`),
  );
}
for (const name of ["launcher-market.png", "qqmusic.png", "pocket-fm.png"]) {
  await copyFile(
    path.join(root, "docs/images", name),
    path.join(output, "media", name),
  );
}
for (const name of ["sdk-counter.png", "sdk-canvas.png"]) {
  await copyFile(
    path.join(root, "website/assets", name),
    path.join(output, "media", name),
  );
}
const sdkVersion = (
  await readFile(path.join(root, "sdk/VERSION"), "utf8")
).trim();
if(process.env.WEBSITE_FETCH_RELEASES === "1") {
  const {syncSDK} = await import("./sync-sdk.mjs");
  await syncSDK(sdkVersion,path.join(output,"data/sdk-release.json"));
}
let sdkRelease;
try {
  const saved = JSON.parse(
    await readFile(path.join(output, "data/sdk-release.json"), "utf8"),
  );
  const expected = `https://github.com/vicliu624/sony-nw-x1000-series-cfw/releases/download/sdk-v${sdkVersion}/x1000-sdk-${sdkVersion}-source.zip`;
  if (
    saved.version === sdkVersion &&
    saved.asset?.url === expected &&
    saved.asset.bytes > 0
  )
    sdkRelease = saved;
} catch {
  /* Until an SDK source archive is published, link to source only. */
}
await writeFile(
  path.join(output, "data/sdk.json"),
  JSON.stringify(
    {
      version: sdkVersion,
      sourceUrl:
        "https://github.com/vicliu624/sony-nw-x1000-series-cfw/tree/main/sdk",
      release: sdkRelease,
    },
    null,
    2,
  ) + "\n",
);
await writeFile(
  path.join(output, "data/catalog.json"),
  JSON.stringify(
    {
      version: (await readFile(path.join(root, "VERSION"), "utf8")).trim(),
      apps,
    },
    null,
    2,
  ) + "\n",
);
if (process.env.WEBSITE_FETCH_RELEASES === "1") {
  const response = await fetch(
    "https://api.github.com/repos/vicliu624/sony-nw-x1000-series-cfw/releases?per_page=30",
    {
      headers: {
        Accept: "application/vnd.github+json",
        ...(process.env.GITHUB_TOKEN
          ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
          : {}),
      },
      signal: AbortSignal.timeout(20000),
    },
  );
  if (!response.ok)
    throw new Error(`Release snapshot failed: HTTP ${response.status}`);
  const { sanitizeReleases } = await import("../src/releases.mjs");
  const releases = sanitizeReleases(await response.json());
  await writeFile(
    path.join(output, "data/releases.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), releases }, null, 2) +
      "\n",
  );
}
console.log(
  `Prepared ${apps.length} release-policy apps and public renderer previews.`,
);
