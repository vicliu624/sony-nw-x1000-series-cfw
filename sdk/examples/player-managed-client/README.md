# Managed player client

This C example uses only the public `player-managed-client` SDK module. Build it
with `startup` and `player-managed-client` in a native-services app definition.
Keep its player/client objects in static or heap storage and run calls on one
serialized worker, not a touch/render callback.

The trusted host must supply an authorized connected stream and its nonzero
generation. This example does not discover services, manufacture a grant, start
Sony's player or connect to a guessed socket path. The descriptor and generation
arguments describe an already-authorized connection; they do not confer access.

```text
player-managed-client --fd 3 --generation 23 snapshot
player-managed-client --fd 3 --generation 23 watch 20
player-managed-client --fd 3 --generation 23 tracks 0
player-managed-client --fd 3 --generation 23 playlists 0
player-managed-client --fd 3 --generation 23 members OPAQUE_ID 0
player-managed-client --fd 3 --generation 23 queue 0
player-managed-client --fd 3 --generation 23 pause
```

Each invocation needs a fresh host-authorized session. The numeric values above
are examples, not device constants. Other explicit controls are play, next,
previous, volume-up and volume-down. Unsupported operations return an error; no
control is retried automatically. ACCEPTED is admission, not observed playback.

Watch obtains a synchronized snapshot/event boundary, then queries notifications
at250ms intervals. A changed event causes another synchronized observation. Failed
reads are not displayed as current data; event errors stop this example rather
than silently resetting a cursor. This is a bounded worker example, not a UI or
an unsolicited background service.

On exit it requests a session-close receipt before detaching local state. A
transport error is reported as unconfirmed release, never as a successful close.

`tools/test_sdk_player_service.py` checks ARM build/help and C++ syntax.
`tools/test_sdk_managed_channel.py --managed-example` executes snapshot, watch,
all four media views and pause under ARM926 with Sony libc against a separate
sanitized model host, using a fresh session for each case. Watch checks an
independently changed model state and the refreshed observation; pause checks
exactly one provider command. Every case verifies session release and host drain.
The remaining control names and error/recovery CLI paths are not individually
covered by that test; this is not exhaustive example qualification.
No physical player, original-manager grant or firmware installation is tested.
