# Launcher, store and shared runtime

The launcher is implemented in runtime/native. Store frontend, package transactions,
resolver/TLS and original-libc bridges remain in runtime/store because other apps
share them. They are not loose files mixed with the per-app directory.

The launcher dynamically discovers HOMEBREW/apps/<id>/app.ini, verifies package
identity/integrity/ELF and owns child lifecycle and display release/reacquisition.
Default entry and Sony return remain tied to the original manager/proxy protocol.

The store contains local install and network-controller implementations, with
explicit publisher/trust configuration. CI emits a GitHub Release catalog and
matching market-source/player-setup files; see ../RELEASES.md. A setup/review
composition without these files still requires configuration. A local fixture
installation is software evidence, not physical deployment qualification.

Builders include build_libc_frontend.py, build_store_app.py and
build_network_store_app.py. Prefer original-libc device/process and librt monotonic
clock profiles where supported; retain explicit legacy profiles for research.

Installation uses verified user storage, staged writes, hashes and rollback/error
states. Packages do not each receive a Sony Home entry. Do not bypass TLS checks,
trust synthetic CAs, infer USB exclusivity from a masked zero state, or use a new
chroot/container/security architecture as a prerequisite for ordinary homebrew.

## Application list artwork

The launcher and market share runtime/native/app_list_art.h: six 52-pixel rows,
36-pixel color icons, proportional 14-pixel Noto ASCII titles, short descriptions,
page indicators and a restrained dark palette. Touch targets, page gestures and
child lifecycle are unchanged. Market rows retain their catalog version in the
secondary line. Long labels end with an ellipsis. Installed custom
names remain visible; the market uses titles supplied by the catalog.

Each application owns its app.json and assets/icon.svg/icon.png under
runtime/apps/<id>. Release composition creates presentation.bin and includes it
in the package inventory. The launcher reads this bounded resource from the
installed application directory. It contains a title, summary and 36-pixel RGB565
icon; unknown IDs need no launcher registration. Missing or malformed resources
use a generic icon. Market titles and descriptions come from catalog metadata,
not an embedded per-ID description table. Remote icon acquisition is still being
migrated; do not claim the market already downloads package-provided artwork.

Regenerate assets with tools/build_launcher_art.py (optional PC-only Pillow13.0.0
and the pinned Noto input). Normal CI consumes the committed generated headers.
Noto raster data retains the SIL OFL notice under third_party/qqmusic-stb/Noto-OFL.txt;
launcher/store packages include that notice. Use tools/render_launcher_preview.py
after the launcher build to produce actual ARM framebuffer previews in
work/launcher-icons-preview. These previews do not access a player.

tools/build_app_list_review.py compiles both binaries against the verified stock
libraries, checks safe CLI entries, and creates a local launcher/store-only review
ZIP under dist/<VERSION>/app-list-review. It does not publish a release, change
repository configuration, access a player or create firmware.

## Details and version management

Selecting an app fetches and verifies its small manifest/index before showing
details. No package payload is downloaded until explicit approval. About and
Changes tabs have bounded word wrapping and pagination; the page displays the
installed version, available version, channel and payload download size.
HBSTORE3 supplies authenticated title, summary, description and version-specific
changes through the pinned catalog. Existing HBSTORE1/HBSTORE2 sources still work:
known apps use a compiled introduction, while missing version-specific notes are
explicitly reported. Sources cannot execute markup or scripts through descriptions.

The selected installed bundle is verified in full before version comparison.
SemVer2.0 precedence handles numeric components, numeric prerelease identifiers,
stable releases and ignored build metadata without integer overflow.

| Local state | Action |
| --- | --- |
| App absent | Explicit download and install |
| Same version and exact bundle identity | Up to date; explicit reinstall allowed |
| Available version is higher | Explicit update |
| Installed version is higher | Downgrade with an extra warning/confirmation |
| Same precedence, different bundle identity | Blocked; publisher must bump version |
| Invalid local bundle or opaque legacy version | Blocked; inspect/recover on PC |

Download completion still requires separate installation confirmation. Immediately
before transaction recovery/staging, the installer holds its existing lock and
rechecks the exact installed identity (or expected absence). A changed app returns
HB_INSTALL_CHANGED; reopen the market to review again. This excludes cooperating
installers, not arbitrary concurrent USB/PC writes; existing platform ownership
checks remain required. Staging, hashes, original transaction recovery and rollback
behavior remain in use. No damaged/unknown directory is silently deleted.
Existing per-app installation/recovery markers block a new market action; resolve
that transaction through the recovery/PC path before comparing versions again.
Personal data belongs outside the replaceable app directory. Downgrading does
not provide a save-format migration or guarantee older-app compatibility.

The selected repository remains an explicit immutable release snapshot. To browse
an older/newer snapshot, install its market-source.zip configuration on the PC.
There is no automatic moving-latest source or on-device release-history picker.
The running market continues to be updated from the PC rather than replacing
its own executable. Uninstalling apps is outside this version-management flow.

Offline checks: tools/test_market_versions.py covers host sanitizers and original
ARM libc state/guard cases; tools/test_release_market.py performs real ARM list,
details, HTTPS redirects, download and transactional new/reinstall/update/downgrade
journeys. tools/render_market_details.py renders the same ARM detail painter.
These are computer-side checks, not physical-player qualification.
