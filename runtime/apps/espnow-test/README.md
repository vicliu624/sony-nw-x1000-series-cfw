# Autonomous ESP-NOW native test

Local ARM review candidate for Japanese X1060/JP1.11. Build with
`python runtime/apps/espnow-test/build.py`. No player action is part of building.
This is an explicit CLI execution engine, not an installed graphical application.

The detached worker does not depend on WiFi Terminal after launch. It gives a
three-second start delay, captures the original network configuration in RAM,
disconnects through Sony's manager, loads the exact full-radio RAM candidate,
executes its local test window, drains pending operations and restores the stock
image/initialization/network. Only then does it finish. Test results survive the
loss of Terminal in an exclusive bounded journal on verified user storage.

Two explicit modes take a12-hex unicast peer MAC and both operator confirmations:

```
espnow-test.arm --detach-rx PEER_MAC12 --charger-confirmed --exclusive-radio-confirmed
espnow-test.arm --detach-tx PEER_MAC12 --charger-confirmed --exclusive-radio-confirmed
```

These are future live-test commands, not instructions to run this unqualified
candidate now. No-argument/invalid invocations perform no radio action. The
operator confirmations do not establish APF/USB/sleep exclusion. The cooperative
socket prevents another custom owner, not original Sony hardware ownership.
There is no installation, flashing, NVP write or system-path log fallback.

RX observes for60 seconds and keeps the first matching-source Protected Action
record without decrypting it, if hardware admits it. Plaintext does not consume
the encrypted capture slot. RAW_ACTION has no FCS; --fcs must not be used when
analyzing these records. tools/analyze_espnow_capture_log.py accepts the journal
directly with an explicit known-LMK file and still requires MIC authentication.
TX sends ten unencrypted binary cases, serially: v1 lengths0/1/249/250 and v2
lengths0/1/250/251/1469/1470. Byte i of case k is(i*17+k)&255. Actual MAC completion
is recorded; it does not prove application delivery. Cardputer reception must
be compared separately. Encrypted interoperable TX is not yet qualified.

The window includes startup and requests recovery at its deadline. It never
kills an in-flight Sony request, force-frees a submitted packet or unloads before
drain. Therefore the deadline is not a guarantee that blocked original APIs will
return within60 seconds. Restoration error retains the process/client and writes
repair-required; only an explicit SIGUSR1 requests a restore retry. Ownership
uncertainty is retained for inspection, never reported as successful recovery.

Logs are newly created as `/contents/HOMEBREW/data/espnow/full-rx-...` or full-tx
records, capped at8192 bytes. Existing directories must already be present on
the verified FAT user volume. Logging failure before mutation refuses startup;
after mutation it requests recovery rather than abandoning radio state. Saved
credentials/LMKs are not written to these logs. A raw record contains test traffic.

The exact candidate uses `/contents/HOMEBREW/data/espnow-test/candidate`, separate
from the legacy chat's candidate directory. This executable links the original
loader implementation with that explicit build-time directory profile; stock
restoration still uses /lib/modules. Default legacy loader behavior is unchanged.
No deployment script is supplied and no existing candidate is overwritten.

Host sanitizers and ARM/original-libc engine tests use the actual full controller,
endpoint and backend with synthetic radio words and modeled Sony effects.
Physical image loading, unknown-key admission, APF/USB/sleep and post-restore
authenticated host reachability remain unqualified. Do not report this as full
ESP-NOW acceptance or as a fix for the earlier Wi-Fi interruption.

## Encrypted modes

The separately installed alpha.2 worker adds `--detach-enc-tx`,
`--detach-enc-rx` and `--detach-enc-tx-resume`, with the same MAC and operator
arguments. The key input is exactly32 bytes (PMK followed by API LMK) at
`/contents/HOMEBREW/data/espnow-test/session.keys`; counter records live in its
`pn/` directory on verified user storage. No system destination is used.
Fresh modes refuse existing key scopes; resume reuses their durable counters.
Never reset a scope to reuse its key. Rotate keys for independent experiments.

Physical alpha.2 evidence establishes encrypted TX through1470 bytes, same-key
process restart with retained peer and continued PN, and authenticated1470-byte
RX with an exact payload digest. These observations do not qualify arbitrary
power loss, sleep, USB handoff, all peers or full protocol completion. The raw
`--detach-rx` mode remains a capture mode, distinct from authenticated encrypted RX.

Alpha.3 additionally provides `--detach-enc-rx-resume`: it loads the existing
receive high-water record for the same key scope without provisioning or resetting
it. This enables a separate process to continue enforcing the durable replay floor.
It does not by itself prove physical restart or replay acceptance.
