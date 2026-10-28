import { writeFile } from "node:fs/promises";
const repository = "vicliu624/sony-nw-x1000-series-cfw";
export async function syncSDK(version, destination) {
  const tag = `sdk-v${version}`;
  const response = await fetch(`https://api.github.com/repos/${repository}/releases/tags/${tag}`, {
    headers: { Accept: "application/vnd.github+json", ...(process.env.GITHUB_TOKEN ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}) },
    signal: AbortSignal.timeout(20000),
  });
  if(response.status === 404) { console.log("SDK archive is not published yet; developer portal links to source."); return; }
  if(!response.ok) throw new Error(`SDK release refresh failed: HTTP ${response.status}`);
  const release = await response.json();
  const filename = `x1000-sdk-${version}-source.zip`;
  const url = `https://github.com/${repository}/releases/download/${tag}/${filename}`;
  const matches = release.assets?.filter(a => a.name === filename && a.browser_download_url === url && Number.isSafeInteger(a.size) && a.size > 0);
  if(release.draft || release.tag_name !== tag || matches?.length !== 1) throw new Error("SDK release identity is incomplete");
  const asset = matches[0];
  const snapshot = {version,url:`https://github.com/${repository}/releases/tag/${tag}`,asset:{url,name:filename,bytes:asset.size,sha256:/^sha256:[a-f0-9]{64}$/.test(asset.digest)?asset.digest.slice(7):null}};
  await writeFile(destination,JSON.stringify(snapshot,null,2)+"\n");
}
