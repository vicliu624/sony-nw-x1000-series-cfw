# Original-player client (unreleased)

Select the player-client module in a native-services application. It supplies
C/C++ headers, the bounded client/provider contract and local IPC client. It does
not contain Sony fixed-address bindings, a radio protocol, a player replacement,
a firmware installer or an automatic background process launcher.

The client requires an independently prepared matching original-player service.
That service must keep SpiderApp running and pump its owner loop. A Homebrew
launch profile that suspends SpiderApp cannot provide playback control through
this endpoint while it is suspended. No service has been installed or physically
qualified by these source changes. Binding an absent endpoint returns an error;
never report success just because the SDK application starts.

## Build

Use the SDK version recorded in sdk/VERSION for the application pin. Add
startup and player-client to sdk.modules in the native-services app.json;
use the existing custom-main build recipe described in SERVICES.md. Its source
set links only client.c, rpc_wire.c, rpc_posix.c and the original libc clock
adapter. SDK setup --services supplies pinned original librt/pthread locally.
Sony libraries are excluded from SDK/application archives.

```c
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>

static struct xw_player player;
static struct xw_player_remote connection;
static volatile int stopping;

/* Run from the application's own worker/event loop, not its rendering callback. */
int connect_player(void) {
    return xw_player_remote_bind(&player, &connection,
                                XW_PLAYER_RPC_ENDPOINT, 250, &stopping);
}
```

Zero-initialize both objects before first bind. Keep them in static or heap
storage: the current ARM build uses14440 bytes for xw_player and27160 for
xw_player_remote. These include fixed scratch buffers, are not small stack
objects, and do not grow per query. Rebuild against matching headers; no binary
layout compatibility is promised. The timeout is1..5000 milliseconds
for one connect/write/read exchange; choose it to suit the application. Calls are
synchronous and bounded by that deadline, so run them away from latency-sensitive
rendering. Cancellation requests stop an exchange; no socket persists between
calls. Use xw_player_close after a successful bind before reusing these objects.

## Controls and observation

Build an xw_player_command with PLAY, PAUSE, NEXT, PREVIOUS or STEP_VOLUME (+1/-1)
and call xw_player_command. Check the negotiated provider.commands mask before
showing optional operations. SET_VOLUME and PLAY_ITEM exist in the contract but
are not bound by the current original provider. UNSUPPORTED is explicit.
ACCEPTED means the original handler accepted the request, not that playback has
completed. UNCERTAIN must not cause automatic replay of a skip or other
non-idempotent operation.

xw_player_snapshot reads state without changing notification history.
xw_player_poll compares observed snapshots and returns a changes mask for state,
track, metadata, volume and available library/queue revision fields. It is polling,
not a lossless event subscription. Read only fields present in snapshot.valid;
unknown state is not paused, and unavailable metadata is not an empty title.
Current title/artist/album come from the original media database rather than an
application parsing only ID3. Position/duration units remain unqualified and are
not advertised as valid by the original provider.

## Media pages

Use xw_media_browse with TRACKS, empty container, a positive limit up to16 and
an offset. Initial native reads return BUSY; retry browse later without changing
request parameters to collect the completed page. Native source loss and query
errors are distinct. Output stays unchanged on failure. This retry rule applies
to reads, not to commands.

Opaque IDs are not paths or row numbers. revision0 means unknown and makes no
cross-page consistency promise. A nonzero expected_revision must match; otherwise
STALE leaves caller data unchanged. Total may be XW_MEDIA_TOTAL_UNKNOWN.
The analysis host now routes PLAYLISTS and PLAYLIST_TRACKS to the experimental
FORMAT3 native list/child reader. This mapping follows the observed original
view5 query shape; its active-menu association and real SonicStage compatibility
remain unqualified. Treat this as a development prototype, handle refusal/errors
and do not advertise physical playlist compatibility from these tests.

The combined GUI/Met analysis host now routes QUEUE through matching-session
capture and background reads for OneGrp with MmTrk or prepared MmOneTrk sequences.
The analysis worker also has an incremental unshuffled MmGrp path; real group
identity/order still require qualification, and shuffled groups are refused.
A GUI-only/absent/unqualified host does
not acquire this capability by installing the client. Handle UNSUPPORTED and
UNAVAILABLE explicitly. A directory scan is never substituted for these views.

Native library and queue revisions remain0 (unknown). The polling change mask
therefore cannot report every queue or catalog edit. Track/state/metadata/volume
changes are observed separately; revision-based invalidation must not be claimed
where the provider has no qualified revision. Retry bounded page reads as needed,
and do not assume unchanged revision0 establishes cross-page consistency.

## Verification and current boundary

Run tools/test_sdk_player_service.py to build an external C consumer through the
actual SDK service compiler, execute cancellation/closed-state checks under
ARM926 with original Sony libc, and syntax-check the public declarations as C++.
Its source-closure check excludes native hooks/fixed-address providers from the
client module. Separate core/RPC/native-reader/broker tests cover their respective
code paths. This is computer-side evidence, not physical playback, sleep, USB or
radio coexistence acceptance. The complete implementation status and remaining
research are in PLAYER.md; source exposure is not a claim of SDK feature completion.


For a clean source-archive check, run:

```sh
python tools/test_sdk_bundle.py /path/to/sdk-source.zip \
  --stock-exe /path/to/NW-X1000_V1_11.exe --player-only
```

This verifies the source manifest, extracts a fresh project, prepares dependencies
from the pinned original installer and public inputs, then builds/executes the
public player consumer. It never copies an old work directory or native binding
artifact. Its report explicitly says player-client-only and full_sdk_matrix_run
false; run the command without --player-only for the existing complete SDK matrix.
No endpoint, firmware or device behavior is installed by either check.
