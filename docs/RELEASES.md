# CI, releases and the application repository

The target repository is `vicliu624/sony-nw-x1000-series-cfw`. Local Git uses SSH;
GitHub Actions publishes with its scoped GITHUB_TOKEN, not a committed SSH key.

## Build contract

`tools/ci_bootstrap.py` obtains the pinned Japanese updater and public source/data
inputs, verifies hashes, extracts original libraries and builds the external TLS
library. It does not use an old dist package as an input. Public TLS roots come
from OS-verified chains for the release/QQ hosts; no test CA or private key is used.

`tools/build_release.py --repository <owner/repo> --tag v<VERSION>` builds the
launcher, firmware, apps and metadata into `dist/<VERSION>/release/upload`.
The tag must exactly match VERSION. `--skip-bootstrap` is for an already verified
local input set, not an exemption from stock component checks.

The firmware profile is built from original Japanese1.11 components and current
Homebrew/error-message/process-cache sources. It preserves the original installer,
kernel and initrd, adds the launcher registration/resources, and supplies external
Japanese/English/Simplified/Traditional packs. It is an experimental source-built
profile, not a claim of byte identity with a historical numbered candidate.

## Release contents

- `NW-X1000-<version>-firmware.zip`: NW_WM_FW.UPG and verification information.
- `NW-X1000-<version>-player-setup.zip`: launcher, market, language app/packs and
  repository configuration on visible user storage.
- One `<app>-<app-version>.zip` per native application.
- `catalog.tsv` plus flat, hash-indexed per-file release assets used by the market.
- `market-source.zip`: a pinned catalog snapshot and public CA configuration.
- `terminal-computer.zip`: PC client/pairing tool, with no private identity.
- Source archive, manifests, release notes and SHA256SUMS.

No ROMs, saves, account state, downloaded music, terminal private keys or original
SDK libraries are included in app packages. The firmware itself necessarily
contains modified Sony firmware components; read the original license and use
only the matching Japanese model. Do not flash international/A910/A820 images.

Copy the player-setup files to visible storage before entering the Homebrew menu.
Firmware installation formats the system partition in the original process; a
correct package/hash is not recovery protection. Physical installation/sleep and
all app hardware behaviors remain experimental. This build does not run an updater.

## Market protocol

HBSTORE1 hierarchical sources remain supported. HBSTORE2 adds a flat asset prefix
after the original seven fields. For GitHub Release hosting a logical path is
encoded injectively as `<app-id>--<lowercase-hex(path-bytes)>`; installed paths stay
unchanged. App manifests/indexes and every payload file retain exact size/SHA256
checks. TLS redirects are HTTPS-only, bounded to five hops and use a new verified
connection per host under the original total deadline.

Repository configuration pins a specific release catalog. Install the corresponding
market-source.zip to select another release snapshot. This is explicit source
selection, not unauthenticated moving-latest metadata. The market does not update
its running executable in place; update the market through the PC package path.

Correct device time is required for ordinary HTTPS certificates. Existing Wi-Fi
must be connected through the original platform. Network reachability does not
establish account login or successful installation on every model.

## Terminal and QQ Music

The public terminal package contains no shared private key. After market installation,
use prepare_terminal_identity.py from terminal-computer.zip with explicit --player
and --computer directories. It creates personal files under HOMEBREW/data/terminal;
keep the computer fingerprint and then open the app. Legacy personal packages
with identity files in the app directory remain readable.

The public QQ build uses an installation ID generated once in its verified user
workspace, not a developer's identity, cookies or account. It does not rotate that
ID on a service rejection. Public profile values are not a real-account success
claim; login/download/import/playback qualification remains outstanding.

## Publishing

Pull requests run offline checks without write permissions. Main/manual builds
produce workflow artifacts. A matching version tag, or an explicit manual publish
on that tag, publishes experimental release assets with contents:write permission
confined to the publish job. The pipeline must finish verification before publishing.
