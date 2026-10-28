# X1000 Island website

A bilingual GitHub Pages frontend for the Japanese NW-X1050/NW-X1060 project.
Built with React, TypeScript, Vite and the actual `animal-island-ui` package.
The website does not build firmware, run an updater, access a player or install apps.

## Directory contract

- `src/main.tsx`: hash routes, language selection, firmware selector and app browser.
- `src/content.ts`: English/Chinese product copy, categories and app guide mappings.
- `src/releases.mjs`: public-release sanitization and exact package matching.
- `src/releases.test.mjs`: release-boundary regression checks.
- `src/style.css`: responsive island layout and CSS player illustration.
- `scripts/prepare.mjs`: generates public app data/icons from release-policy inputs.
- `public/data/releases.json`: sanitized, public GitHub Release fallback snapshot.
- `public/data/catalog.json` and `public/media/`: ignored generated public assets.
- `../dist/website/`: ignored production output; no firmware or private data.
- `../.github/workflows/pages.yml`: independent website build/deploy workflow.

## Local development

Use Node.js 22.12 or newer and run from this directory:

```sh
npm ci
npm run dev
npm test
npm run build
npm run test:site
npm run preview
```

Open the printed URL including `/sony-nw-x1000-series-cfw/`. Use `?lang=en`
or `?lang=zh-CN` for a language link and `#apps`, `#firmware` or `#guide`
for direct sections. Language preference is stored locally when available.

The production output goes to `../dist/website`, never `website/dist`.
The production DOM test exercises the compiled JavaScript with synthetic public
release data: language, search/category filters, drawer details, real package URL
matching, model selection and download risk gating. It does not verify visual
layout, physical hardware, live installation or RF/audio behavior.
Set `WEBSITE_BASE_PATH=/` to build for a root domain; the default project
subpath is required for this repository's GitHub Pages URL.

## Data and download behavior

`config/release.json` determines which applications are public release candidates.
Only those apps' metadata, versions and tracked SVG icons are copied. Current
source versions are displayed separately from versions parsed from published ZIPs.
Only exact GitHub release assets can become download links. No guessed filenames
or moving `/latest` URLs are used. Drafts are excluded; experimental prereleases
are included. Missing or ambiguous packages remain unavailable. API SHA-256
digests are displayed when available, with a link to the selected release's
SHA256SUMS. A hash is an integrity value, not a hardware qualification claim.

At runtime, the public GitHub API refreshes the newest 30 releases (including
prereleases). Rate limits, network failures and timeouts leave the bundled
snapshot available, visibly labeled. Reload/build the snapshot with
`WEBSITE_FETCH_RELEASES=1 npm run build` (POSIX shell), or set that environment
variable before running npm in PowerShell. The build fails if a requested refresh
fails instead of silently claiming a new snapshot. No browser token is needed.

Firmware/setup links require an explicitly selected Japanese model and risk
acknowledgment. Applications download to the computer, with installation guidance;
the website makes no one-click installation or recovery guarantee. Firmware and
setup share one selected tag. All packages remain on GitHub Releases; none are
copied into the website. App descriptions reflect maintained source metadata,
while older package behavior must be checked in its release notes.

## GitHub Pages

Choose **Settings > Pages > Source > GitHub Actions** once. The Pages workflow
builds relevant main-branch changes, manual runs and published releases. Pull
requests run checks/build only. Production deployment is restricted to main.
The website workflow is independent of ARM/firmware CI and never publishes
firmware assets. A release created with GITHUB_TOKEN may not trigger another
workflow; the client-side API refresh still discovers it and a manual Pages run
refreshes the bundled fallback.

Expected production URL: https://vicliu624.github.io/sony-nw-x1000-series-cfw/

## Artwork and notices

UI components use animal-island-ui 2.3.0 (MIT); hand-drawn interface icons use
naive-icons (MIT). Preserve the bundled license notice in `public/THIRD_PARTY.txt`.
Nunito and Noto Sans SC are shipped by the component library under SIL OFL;
font licenses are also included. The device illustration is CSS, not a device
photograph. App artwork comes from the maintained app folders. Selected native
renderer screenshots come from `docs/images`; their provenance and limitations
are documented there. No account data, ROMs, saves or Sony binaries are copied.
