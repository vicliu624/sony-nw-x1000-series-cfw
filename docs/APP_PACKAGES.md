# Application packages and storage

Visible user storage contains `HOMEBREW/apps/<id>/app.ini`, a native `app` ELF,
resources and `files.sha256`. Apps are discovered inside the launcher, not added
as separate Sony Home items. Expected target is `sony-nw-x1000-jp`.

Example manifest:

```ini
api=1
id=hello
name=Hello
version=0.1.0-dev.17
target=sony-nw-x1000-jp
exec=app
bytes=<actual executable length>
sha256=<actual executable SHA-256>
```

The file index starts with `HBFILES1`, followed by hash, byte length and relative
path per entry. It must describe actual package files; generated checksums are
not credentials or a substitute for publisher trust. Reject traversal, unknown
inventory, corrupt bytes and unsupported target/ELF before execution.

New release packages also contain app-info.json, presentation.bin and icon.png
(with an optional editable icon.svg), covered by
the same file inventory. app.ini stays at api1 with its strict existing fields;
descriptions are not added as unknown manifest keys. HBSTORE3 catalog metadata
provides the bounded detail-page content before downloading package payloads.
Application versions use SemVer precedence. A changed file inventory requires a
higher app version, even when executable bytes did not change. Project release
VERSION and independently versioned apps have separate responsibilities; see
RELEASES.md for the publishing gate and apps/STORE.md for installed-state policy.

Use staged writes, verification and rename/rollback. Preserve app data outside
the replaceable executable tree, normally `HOMEBREW/data/<id>/`. Keep identity and
generation state consistent across retries. A successful rename without directory
sync may still require an explicit uncertain-state report.

Mount verification must establish the actual user device, not only a /contents
prefix. On the test player it is `/dev/mtdblock/2` mounted vfat at /contents.
Check path/device identity, hardlinks/symlinks and storage reserve. Do not fall
back to the root filesystem or a system-backed temporary directory.

USB storage export refers to that same device. A process-local lock or a masked
USB query does not exclude host access. Suspend/stop work and coordinate with the
original lifecycle before allowing export. Never modify an unknown Sony database
to force imported media to appear; database writes may target /db.

Computer deployment scripts must verify the selected Sony volume and previously
confirmed USB identity, allowlist exact destination files, back up replacements
and read back hashes. Copying a verified file is deployment evidence, not RF,
audio, lifecycle or recovery qualification. No installer should print private keys.
