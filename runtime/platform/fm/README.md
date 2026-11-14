# Receiver model and stock FM adapters

The `fm` SDK module contains a receiver model, Si470x wire adapter, session
coordinator and explicit native transport. Pocket FM owns touch controls,
presentation, preferences and persistence under `runtime/apps/fm-radio/`.

| Interface | Responsibility |
| --- | --- |
| `fm_model.h` | Integer-kHz bands, bounded station lists and cancelable scan state |
| `fm_tuner.h` | Fixed ARM32 V4L1 layouts, stock tuner identity, tune confirmation and band restoration |
| `fm_session.h` | Coordinate caller-owned tuner/audio resources, cancellation and cleanup |
| `fm_native.h` | Explicit original-libc device operations for an already-qualified native caller |

A native device open can initialize hardware. These interfaces do not establish
ownership, implement Sony handoff or authorize concurrent use with the original
player. The caller must supply qualified acquisition and close callbacks; the
native hardware handoff remains unqualified. Default help/selftest paths must
never start it.

Initialize a fresh zeroed session and serialize start/update/stop. An open callback
that fails releases its own partial handle. A close callback consumes the handle
even on error; retrying `close(fd)` can close a reused descriptor. Cleanup retains
resources while tuner quiesce/band or mixer restoration needs retry. A consumed
close failure blocks a new start and is not silently cleared.

Stopping discards an incomplete scan without issuing an extra restore-frequency
tune during cancellation. A completed scan commits only after successful tune
restoration. Band limits describe the requested software/backend contract;
neither the range nor a model signal value proves reception.

The native adapter calls the pinned `ioctl` symbol and an explicit request
allowlist. It does not use modern time64/V4L layouts or the unsafe stock GETREGALL
copy-size contract. Driver requests and original behavior are unchanged by source
organization.

`python tools/build_app.py fm-radio --output work/my-fm-check` builds and runs the
existing fake-transport/storage/UI tests. It executes only safe CLI entries of
the native candidate. No player is opened; RF, acoustic output and restoration
remain separate physical acceptance.
