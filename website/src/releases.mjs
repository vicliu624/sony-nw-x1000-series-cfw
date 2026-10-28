export const REPOSITORY = "vicliu624/sony-nw-x1000-series-cfw";
export const GITHUB = `https://github.com/${REPOSITORY}`;
const semver = "[0-9]+\\.[0-9]+\\.[0-9]+(?:-[A-Za-z0-9.-]+)?";
export function sanitizeReleases(input) {
  if (!Array.isArray(input)) throw new Error("Invalid release list");
  return input
    .filter(
      (r) =>
        r &&
        !r.draft &&
        new RegExp(`^v${semver}$`).test(r.tag_name) &&
        Array.isArray(r.assets),
    )
    .map((r) => ({
      tag_name: r.tag_name,
      name: typeof r.name === "string" ? r.name : r.tag_name,
      prerelease: Boolean(r.prerelease),
      published_at: r.published_at,
      html_url: `${GITHUB}/releases/tag/${encodeURIComponent(r.tag_name)}`,
      assets: r.assets
        .filter(
          (a) =>
            a &&
            typeof a.name === "string" &&
            !a.name.includes("/") &&
            (a.name.endsWith(".zip") ||
              [
                "SHA256SUMS",
                "release-manifest.json",
                "RELEASE_NOTES.md",
              ].includes(a.name)) &&
            Number.isSafeInteger(a.size) &&
            a.size > 0 &&
            a.browser_download_url ===
              `${GITHUB}/releases/download/${r.tag_name}/${a.name}`,
        )
        .map((a) => ({
          name: a.name,
          size: a.size,
          browser_download_url: a.browser_download_url,
          digest: /^sha256:[a-f0-9]{64}$/.test(a.digest) ? a.digest : null,
        })),
    }))
    .sort(
      (a, b) =>
        (Date.parse(b.published_at) || 0) - (Date.parse(a.published_at) || 0),
    );
}
export function firmwareAsset(release, kind) {
  if (!release || !["firmware", "player-setup"].includes(kind))
    return undefined;
  return release.assets.find(
    (a) => a.name === `NW-X1000-${release.tag_name.slice(1)}-${kind}.zip`,
  );
}
export function appAsset(release, id) {
  if (!release || !/^[a-z0-9-]+$/.test(id)) return undefined;
  const pattern = new RegExp(`^${id}-(${semver})\\.zip$`);
  const matches = release.assets.filter((a) => pattern.test(a.name));
  if (matches.length !== 1) return undefined;
  return { ...matches[0], version: matches[0].name.match(pattern)[1] };
}
export function formatBytes(bytes) {
  return bytes >= 1048576
    ? `${(bytes / 1048576).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
