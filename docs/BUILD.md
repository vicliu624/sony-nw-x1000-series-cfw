# Build and offline verification

Run supported Python tools from the project root in Linux/WSL. Device-side builds
use arm-linux-gnueabi-gcc targeting ARMv5TE, ARM mode and soft float. QEMU ARM926
and the pinned original loader/libc provide offline execution. Use each script's
`--help` before supplying a new output/profile; some research scripts are not CLIs.

## Environment

Extracted original loaders need their executable bit when invoked as QEMU's
program. Bootstrap preserves mode0755 without changing their bytes. Windows/DrvFS
can mask a missing mode bit that a clean Linux runner correctly enforces.

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

Original updater EXEs are inspected/extracted, not executed. Rockbox upgtools is
built locally; the Japanese package uses the independently verified key in
KNOWLEDGE.md. Verify original roundtrip before considering modified output.

The original installer formats mtdblock/1 with ext2 before unpacking. A valid
container/hash, small increment or 148MiB model does not establish safe flashing.
Firmware candidates stay local and experimental; this reorganization neither
builds nor installs a new UPG.

## Output policy

Use work for reusable evidence, dist for local delivery packages, and .tmp for
scratch/previews/private notes. All are ignored. Do not write artifacts into docs
or another project. A source package must include required notices but must not
bundle original Sony files, private identities, session codes, ROMs or music.
