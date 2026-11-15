# Device Info

Source: runtime/apps/device-info. Builder: tools/build_device_info.py.

The app owns its read-only data collection, text pages, renderer, touch navigation
and refresh policy. Capacity comes from the original JP1.11 statfs ABI. The
collector uses a process-local scratch buffer and runs serially on refresh.

Reads CPU/kernel/memory, mounted filesystem capacity and MTD layout. Swipe pages,
tap to refresh and use BACK TO APPS to return. `--dump` writes stdout; `--help`,
`--version` and `--selftest` provide safe inspection. Fixture-root selection is
explicit and does not turn host capacity into device evidence.

It does not read raw partitions, write logs or alter device configuration. Proc
sizes and filesystem free space establish different facts; neither proves update
or recovery safety. Keep per-build hardware status separate from the terminal's
independent live measurements.
