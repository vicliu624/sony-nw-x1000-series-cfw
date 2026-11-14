# Build and offline verification

For the original-interface guest and reviewed-candidate root viewer, see
[QEMU preparation and controls](QEMU.md). This PC environment does not flash a
player and cannot qualify physical wireless behavior.

Run supported Python tools from the project root in Linux/WSL. Device-side builds
use arm-linux-gnueabi-gcc targeting ARMv5TE, ARM mode and soft float. QEMU ARM926
and the pinned original loader/libc provide offline execution. Use each script's
`--help` before supplying a new output/profile; some research scripts are not CLIs.

## Independent application builds

Use tools/build_app.py --list to discover application definitions. Apps build
through their local runtime/apps/<id>/build.py; old tools
entry points are compatibility wrappers. See [the application specification](APP_SPEC.md)
for commands, package formats and compatibility limits.

## Environment

Firmware container tools require OpenSSL3 with its legacy DES provider on PATH.
Encoding and decoding use explicit DES-ECB without padding; each operation checks
its reverse and refuses errors without retry or fallback. Run
tools/test_upg_crypto.py for the known-answer/rejection checks and exact original
UPG rebuild. Independent Rockbox component extraction remains a separate check;
a same-backend roundtrip is not firmware qualification. This is PC-only tooling.
The release builder runs this check immediately after verifying bootstrap
components and before building applications or generating release firmware.
A failed codec check aborts the release job; its log is retained with build
diagnostics. This gate does not qualify the private managed-host candidate.

Extracted original loaders need their executable bit when invoked as QEMU's
program. Bootstrap preserves mode0755 without changing their bytes. Windows/DrvFS
can mask a missing mode bit that a clean Linux runner correctly enforces.
CI places work on a separate ephemeral tmpfs volume. Storage fixtures intentionally
reject a data directory on the same device as the system root; do not weaken that
production guard to accommodate an ordinary runner checkout. This is a PC fixture,
not FAT/USB hardware qualification.

Create `.venv` and install requirements.txt; requirements-research.txt adds optional
binary-analysis tools. Builders may require GCC/GCC12, ARM binutils, QEMU user mode,
OpenSSL and ordinary archive utilities. Dependency acquisition must preserve
source revisions, hashes and notices. Sony libraries are local inputs under work,
not package payloads. See THIRD_PARTY.md.

Current builders use these established local inputs where applicable:

- `work/arm-signal-tests/lib/{libc.so.6,ld-linux.so.3}`
- `work/upg-jp/verified-{0,1,2,3}.bin`
- `work/external-tls-probe/arm-build/libbearssl.a` and its matching headers
- Original resolver/librt inputs under `work/stock-resolver-probe/`
- Source/data dependencies under third_party and assets

Do not delete work indiscriminately: it includes dependencies, original evidence
and rollback packages, not just disposable compilation output. Missing inputs
should be acquired/extracted with the existing provenance tools, not substituted
with an unrelated model's files.

## Application entry points

```sh
.venv/bin/python tools/check_repository_layout.py
.venv/bin/python tools/build_terminal.py
.venv/bin/python tools/build_fm_radio.py
.venv/bin/python tools/build_device_info.py
.venv/bin/python tools/build_dictionary_app.py
.venv/bin/python tools/build_ebook_app.py
.venv/bin/python tools/build_emulator_apps.py
.venv/bin/python tools/build_graphics_demo.py
.venv/bin/python tools/build_hello_app.py
```

BSOD Pet uses a locally supplied sprite sheet. See [Pet](apps/PET.md) for asset
conversion, `tools/build_pet.py` and `tools/package_pet.py`. Its artwork is not
downloaded by CI and the local manual-test package is not a public release input.

Large data builders and application builders are separate. EBook/dictionary use
their explicit app VERSION files; project builders use root VERSION. Tool scripts
remain at stable tools paths while native sources are grouped by app.
The legacy app-collection version is retained at config/app-collection/VERSION,
outside ignored generated-package directories.

QQ Music requires an explicit non-account profile and a fresh output directory:

```sh
.venv/bin/python tools/build_qqmusic_native.py --help
.venv/bin/python tools/build_qqmusic_native.py --profile <profile.json> --output work/<new-output>
```

`--device-full` enables the import composition; it is not hardware qualification.
Do not use a synthetic test identity/CA as a production installation profile.
Store/launcher and language builders have explicit composition/output switches;
consult their help and the corresponding app guide.

## Checks after source moves

The layout check validates English docs, links, source grouping and migrated
includes/references. Python compilation catches syntax errors. Relevant builders
then establish actual cross-compilation, stock symbol compatibility, safe CLI
execution and applicable fixture behavior. Do not silently reuse a pre-move source
hash report as a new pass. Saved source/artifact hashes under work are historical.

Avoid running live login, device-install scripts or hardware entry points as
part of a repository check. Tests that need a configured service/account remain
explicit, independent actions. Do not rebuild every binary-analysis experiment
after an unrelated documentation change.

## Firmware research

The release firmware builder verifies the root contents decoded from the final
UPG. `tools/test_homebrew_firmware_icon.py` can repeat the check on an existing
package. Homebrew must use its appended texture 139
in both Home layouts and the compiled catalog count must be140. The texture is
generated from the maintained shadow PNG; stock Settings63 and every original
texture remain unchanged. See releases/0.1.0-dev.22.md for the regression.

Original updater EXEs are inspected/extracted, not executed. Rockbox upgtools is
built locally; the Japanese package uses the independently verified key in
KNOWLEDGE.md. Verify original roundtrip before considering modified output.

The original installer formats mtdblock/1 with ext2 before unpacking. A valid
container/hash, small increment or 148MiB model does not establish safe flashing.
Firmware candidates stay local and experimental. Routine checks do not generate
an update package or install firmware; those are separate explicit operations.

For a managed player layout, build the localized root once and pass it directly
to layout assembly:

```sh
.venv/bin/python tools/release_firmware.py --root-only --output work/localized-root
.venv/bin/python tools/prepare_player_system_layout.py \
  --localization-root work/localized-root/localized-root.tar.gz \
  --host-review work/example/host/build.json
.venv/bin/python tools/review_managed_root_capacity.py \
  --layout-review work/example/layout/report.json
```

The layout records the archive and its SHA-256. Capacity checks, the QEMU layout
loader and final packaging use that same input. Existing layouts that reference
a localized UPG can still be read when their input and source receipts validate.
The final packer uses the verified original installer, kernel and initrd.

For a complete root allocation model without producing firmware, use matching
capacity/layout receipts and a prepared original Sony sysroot:

```sh
.venv/bin/python tools/measure_layout_ext2.py \
  --capacity-review work/example/review.json \
  --sysroot work/example/sony-root
```

The tool creates only new ordinary image files under `work/`, runs the verified
Sony formatter under ARM user emulation and uses host debugfs/read-only e2fsck.
It never mounts an image or accesses a device. Full contents and inode metadata
are read back; inputs and tool sources must remain unchanged during measurement.
The report distinguishes modeled nonreserved margin from physical qualification.
See [system footprint](SYSTEM_FOOTPRINT.md).

For an explicitly requested local diagnostic, freeze an already reviewed UPG
and its matching allocation/regression evidence with:

```sh
.venv/bin/python tools/prepare_diagnostic_materials.py \
  --firmware-review work/example/firmware/review.json \
  --allocation-review work/example/allocation/report.json \
  --regression-review work/example/regressions/report.json \
  --controller-review work/example/core2/build.json \
  --updater-template work/sony-jp-1.11/updater \
  --radio-inputs work/radio-inputs/candidate \
  --output dist/diagnostics/example
```

The firmware review must already have an independent Rockbox extraction under
its `rockbox-check/` directory. The tool checks all original installation
components, the complete root inventory, allocation inputs and original updater
identities. Product runtime/SDK/config sources must still match the passing
regression snapshot. Subsequent PC-only changes are listed explicitly.
Use reusable local inputs for the updater and external radio files. The updater
executables, INI and stock UPG must match the original Japanese 1.11 hashes.
The radio files must match the sizes and hashes recorded by the selected owner.
It preserves an original Sony package, adds only reviewed immutable external
RF inputs and a fresh bounded diagnostic record. The directory, ZIP and checksum
are staged beside the destination. The ZIP's inventory and file hashes are
checked before publishing. A failed attempt clears its staging files and leaves
previous deliveries available.
No pairing keys, configuration or PN journals are supplied. Copying external
files and running the unchanged updater remain manual device operations.

Negotiated-link firmware requires `--controller-review`. The packer verifies
the controller image, the native archive linked by Root and identical link
protocol source/header hashes. It includes only the Core2 application image
and build receipt under `04_CORE2`; no bootloader, partition table or NVS is
supplied or written. Instructions use the selected version and allocation
model. Omit this argument only for a legacy transport profile.

## Output policy

Use work for reusable evidence, dist for local delivery packages, and .tmp for
scratch/previews/private notes. All are ignored. Do not write artifacts into docs
or another project. A source package must include required notices but must not
bundle original Sony files, private identities, session codes, ROMs or music.

## Shared Wi-Fi candidate

The two-choice Wireless Mode menu is composed only when
`build_player_host.py --shared-wifi-review` is supplied with a matching
native Remote page and shared-owner supervisor profile. The ordinary release
build does not select this private profile. Use the verified radio overlay
receipt from `prepare_shared_wifi_image.py` and pin the matching owner and
supervisor artifacts together. Existing pairing state and packet-number
journals belong on the player volume and must carry forward for the same keys.

Before qualifying the candidate, replay the final Wireless Mode page with
`test_wireless_mode_refresh.py` and the deferred Off action with
`test_shared_wifi_auto_off.py`. Use independent Rockbox extraction to compare
the updater script, kernel and initrd against the baseline. Run the root
capacity review separately.

For the first hardware check, enable Wi-Fi without joining a router and use a
matching Core2 on the observed radio channel. Confirm state and controls, then
turn Remote off and test USB. Router association is a separate coexistence case.

For that coexistence case, keep the X1060 in the native player and establish
ordinary network traffic with Wireless Remote off. Use a Core2 on the router's
current 2.4 GHz channel. Confirm the Core2 receives playback state and a
play/pause command takes effect while network traffic still works. Then turn
Wireless Remote off and confirm network traffic continues. Finally, with the
remote active again, select Wireless Mode Off once and confirm both the remote
and ordinary Wi-Fi stop. `Watch-SharedWifiTrial.ps1` can correlate Core2 receive
counters and IP reachability. Reachability is meaningful only after a working
baseline with verified player identity, and does not measure RF power.
