# NW-X1000 project rules

Read README.md, docs/KNOWLEDGE.md, docs/STATUS.md and the relevant app guide first.
Target Japanese NW-X1050/NW-X1060 only. Do not edit sibling projects as a side effect.

## Layout and documentation

- Each external app has a runtime/apps/<application> folder. Shared launcher,
  platform and package/libc/network adapters stay in runtime/native,
  runtime/platform and runtime/store.
- Device code is C/C++ with necessary ARM startup/ABI assembly. Python is PC-only.
- Project documentation must be English. Preserve multilingual product data and
  upstream licenses. Consolidate durable facts instead of adding session diaries.
- Private evidence, screenshots, scratch and superseded notes belong in ignored
  .tmp/. Reusable local inputs and test output belong in ignored work/.
- Use VERSION for project identity and retain existing per-app versions. Source
  moves invalidate old source hashes; never relabel old reports as new passes.

## Platform and storage

- Preserve Sony's kernel, initrd, updater and installation behavior. Do not assume
  A910/A820 keys, ABI, capacity, ioctl or recovery mechanisms apply.
- Direct ARM syscalls require the verified OABI convention. Preserve libc/stat,
  time and signal bridges; modern time64 structures are not stock ABI.
- Apps and their state belong on verified exposed user storage. Validate mounts,
  device identity, symlinks, space and USB ownership; no system-path fallback.
- QQ account/session state, QR images, source/output music, artwork, logs,
  manifests and partials must remain on user storage. Do not use system-backed
  /tmp as persistence. Audit database destinations before a stock library refresh.
- Preserve original firmware, rollback packages and failure/recovery evidence.
  Do not commit Sony binaries, private device data, ROMs or seed saves.
- Normal network research is permitted. Preserve TLS hostname/CA/time validation;
  do not import another client's cookies, identity or private cache.

## Scope and checks

- Current maintenance is PC-side. Earlier authorization for a specific app or
  hardware test is not blanket authorization for flashing, NVP/partition edits or
  unrelated device writes. Explicit user instructions override older notes.
- Do not initialize/publish a repository or publish packages unless requested.
- QEMU, capacity models and synthetic devices are not hardware qualification.
  Keep RF/audio, sleep/wake, USB handoff and recovery limits explicit.
- Update builders, fixtures and includes when moving files. Run
  tools/check_repository_layout.py, syntax checks and applicable offline ARM
  builds/tests. Do not make live account/device actions a side effect of checks.
