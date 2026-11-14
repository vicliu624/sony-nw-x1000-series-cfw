# Explicit device research probes

These C programs are research inputs, not launcher apps or public SDK examples.
Normal firmware/application builders do not install or run them. Their separate
PC builders prepare finite reviewed artifacts under ignored `work/`.

| Source | Purpose | Builder |
| --- | --- | --- |
| `launcher_entry_probe.c` | One process-entry marker in a preallocated nonce-matched user file | `tools/build_launcher_entry_probe.py` |
| `launcher_capture.c` | Bounded launcher diagnostic capture to a preallocated user file | `tools/build_launcher_capture.py` |
| `remote_start_probe.c` | Read-only queue state from an explicitly selected, hash-matched player | `tools/build_remote_start_probe.py` |
| `space_probe.c` | Read-only fixed partition-capacity report | `tools/build_device_space_probe.py` |
| `radio_receive_probe.c` | GET-only chip/queue counters after checking the compiled radio profile | `tools/build_radio_receive_probe.py` |

Building is not authorization to deploy or execute. Probe-specific read/write
scope and exact input hashes must be reviewed before any device test. The remote
queue probe is bound to a retained historical image, not arbitrary current
firmware. Preserve old receipts; moved source requires fresh compiler receipts.
