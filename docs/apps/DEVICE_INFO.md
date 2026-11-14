# Device Info

Source: runtime/apps/device-info. Builder: tools/build_device_info.py.

The app owns its renderer, touch navigation and refresh policy. Shared read-only
collection and the original statfs ABI adapter live in
`runtime/platform/system-info/`, exported as the SDK `system-info` module through
`x1000/services/system_info.h`. This module does not depend on the app's source
or build recipe. Its bounded text-page snapshot is intended for diagnostics;
collection uses a shared scratch buffer, so callers must serialize it. A capacity
snapshot is not storage ownership, a reservation or permission to write.

Reads CPU/kernel/memory, mounted filesystem capacity and MTD layout. Swipe pages,
tap to refresh and use BACK TO APPS to return. `--dump` writes stdout; `--help`,
`--version` and `--selftest` provide safe inspection. Fixture-root selection is
explicit and does not turn host capacity into device evidence.

It does not read raw partitions, write logs or alter device configuration. Proc
sizes and filesystem free space establish different facts; neither proves update
or recovery safety. Keep per-build hardware status separate from the terminal's
independent live measurements.
