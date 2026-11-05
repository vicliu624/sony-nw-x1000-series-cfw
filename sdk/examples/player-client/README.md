# Player client example

This C command-line consumer uses only the public player-client service. It
does not install a backend or change firmware. Run it only after a matching
original-player service has been separately prepared and approved for the device.
An absent service returns an error; the example never starts one.

Select startup and player-client in a native-services app.json, pin the version
from sdk/VERSION and use main.c as the sole local source in build.json. See
docs/sdk/SERVICES.md and docs/sdk/PLAYER_CLIENT.md. The maintained
tools/test_sdk_player_service.py builds this example with the actual SDK compiler
and executes its --help path with the original Sony loader/libc under ARM926.
That check does not establish a working device endpoint.
The host tools/test_player_broker_rpc.py additionally runs the example's controls,
snapshot/watch and media pages against real local IPC and production broker/
reader code, with native player and database results modeled.

Examples after building:

```sh
./app snapshot
./app watch 20
./app tracks 0
./app playlists 0
./app members '<opaque playlist ID>' 0
./app queue 0
./app pause
./app play
./app next
./app previous
./app volume-up
./app volume-down
```

Use --endpoint NAME before the operation to select an explicitly configured
local endpoint. Arguments are validated before binding. Commands are issued
once, including when the result is UNCERTAIN. ACCEPTED is admission, not proof
of playback. Observe the resulting state separately.

Watch reports observed changes and marks failed reads as stale; it is not a
lossless event stream. Its250ms delay follows each synchronous read, whose
deadline is3000ms. Large objects use static storage. No state files are written.

Browse requests fetch one page of at most16 rows. BUSY means retry the same
read later; this example exits with the result so the caller chooses when.
Use next_offset for another request. revision0 and total4294967295 mean unknown;
do not infer consistency or an enormous library. Native playlist/queue support
is experimental and may return UNSUPPORTED or UNAVAILABLE. Text is UTF-8 and
may contain terminal control characters from user metadata; render it as data
in a graphical application. The example's console output is not a wire format.
