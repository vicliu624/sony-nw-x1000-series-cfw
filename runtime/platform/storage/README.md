# User-volume observation and preflight

This module checks an existing directory on the exposed user volume. It owns
mount-table validation, root/user device separation, directory descriptor and
inode observations, free-space queries and conservative allocation planning.
It creates no files or directories and performs no account or media operations.

Public source interfaces are `x1000/services/volume.h` and `volume_policy.h`.
The `qq_volume_*`, `qq_storage_*` symbols and `qqmusic_*` filenames are retained
for source/ABI compatibility. Their implementation is shared; it does not depend
on the QQ Music app. Account identity, staging, publication, conversion and import
job policy remain in that application.

Initialize a fresh observer, open the existing workspace with an independently
qualified source policy and budget, recheck before a transaction, then close it.
The caller serializes operations and owns the directory descriptor until close.
The last-failure diagnostic has single-controller scope. Do not copy a live
observer or treat its descriptor as a transferable ownership grant.

A successful observation is a snapshot. It does not reserve space, exclude USB,
prevent unmount or authorize writes. Writers still need their own qualified
ownership and descriptor checks. Failure must not select a system-backed path.
The callback SDK's unknown-ownership result remains unchanged.

The existing plan has six byte/file-count categories plus reserve and directory
allocation units. The historical source/decoded/mp3 labels retain their original
meaning for import clients; this is not a general transaction manager. File counts
matter because each file can consume a separate allocation unit. Preserve overflow
checks and retained-source peak accounting when adapting a new caller.

Offline checks:

```sh
python tools/test_qqmusic_storage.py
python tools/test_qqmusic_volume.py
python tools/test_sdk.py
```

The first checks normalized observations and arithmetic. The second uses real
host file operations with explicit mount/path fixtures and runs the ARM variant
through the pinned Sony libc. Neither qualifies physical FAT durability or USB
handoff. Read [the SDK storage contract](../../../docs/sdk/API.md#data-and-resources)
before using these helpers in an app.
