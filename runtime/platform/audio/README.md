# Original audio routing

The `audio-route` SDK module implements the original mixer snapshot, muted
preparation and restoration contract. FM sessions and PCM clients consume this
shared implementation. It contains no app UI, preferences or device opening.

The caller supplies an already-owned transport after a completed Sony audio
handoff. Preparing a struct is not that handoff. Calls are serialized, and a dirty
snapshot must be restored before another prepare. Unresolved restoration retains
dirty state; it does not grant a new session.

Preparation requires an already-powered codec and a representable initial mute
state. The public mute operation cannot restore driver-private bit `0x100`.
Routing and mix fields are read back after writes. Analog headphone volume is
not changed. Restore attempts every saved field and unmutes only after the
restoration succeeds. The implementation adds no codec reset or guessed power
operation.

App and SDK builds use the same C functions and fixed Japanese 1.11 ioctl values.
The model tests do not prove physical audio, DSP quality, power state or original
player restoration. See [FM](../fm/README.md) and the public
[native services](../../../docs/sdk/SERVICES.md) before selecting a hardware path.
