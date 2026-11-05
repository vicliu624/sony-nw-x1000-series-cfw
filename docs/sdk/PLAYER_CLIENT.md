# Original-player client (unreleased)

SDK0.2.0-alpha.9 development also offers player-managed-client and public
player_managed.h. This optional module binds only a manager-supplied authorized
descriptor; it never starts a backend. The ordinary player API handles controls,
snapshot/poll and browsing; managed methods add status/sync/events/end. See
[lifecycle contract](LIFECYCLE.md) for end versus detach and remaining platform
acceptance. The original manager descriptor-delivery path is not implemented.
This source export is not device service availability or a published release.

In the full checkout, tools/test_sdk_managed_channel.py builds an external ARM
consumer using only public SDK headers and the player-managed-client module.
A separate sanitized host server transfers an inherited local descriptor; the
ARM client runs with original Sony loader/libc/librt and exercises controls,
media, snapshot/event synchronization, status and confirmed end. Native backend
results remain modeled. This test's server is research infrastructure, excluded
from source SDK bundles; it does not implement original-manager authority.

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

Original command3 completion also reaches Moma plugin/library finalizers. The
experimental host's media workers require verified pre-finalize revoke/drain
coordination; pumping or detecting source loss after teardown is insufficient.
That native coordination is not installed. Foreground loss alone does not prove
OS process suspension; the exact switch/cleanup path must be qualified.

The full checkout now has an optional C exec activation building block, described
in [the implementation guide](PLAYER.md#optional-exec-activation-building-block).
It is default-off and uninstalled. Its original-loader process-identity tests use
a C probe payload. A separate original-manager test passes registration and
switch/return with a C Home replacement; full SpiderApp startup remains
unqualified. The
client module/source archive does not install or activate that bootstrap.

## Build

A complete C consumer is provided at sdk/examples/player-client/main.c with
usage and integration notes in the adjacent README.md. It supports explicit
controls, bounded change polling and one-page track/playlist/member/queue reads.
It contains no radio protocol, state persistence or backend installer. The SDK
test builds it through the native-services compiler and runs --help with the
original Sony loader/libc; real endpoint behavior remains a separate check.
The host broker/RPC test also runs this exact example as independent processes
for snapshot/watch, all six controls and track/playlist/member pages, using real
local IPC and production client/broker/readers with modeled native data. It
retries only pending reads. This is not a physical-player service test.
tools/test_player_broker_system.py also executes the exact example's snapshot,
watch and six controls as separate original-libc ARM processes in the isolated
kernel guest, followed by the existing selection/media client and worker drain.
Native player/media/GUI remain modeled; the guest kernel is not Sony's kernel.

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
                                XW_PLAYER_RPC_ENDPOINT, 3000, &stopping);
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

The example uses3000ms because one traced original GUI idle policy waits200ms
and large browse responses span multiple bounded service ticks. This is not a
physical latency guarantee. A command request's queued header/body are read in
the same tick where possible; the server still performs at most one provider
operation and sends at most2048 response bytes per tick. Short deadlines can
still produce UNAVAILABLE or UNCERTAIN; they must not trigger silent replay.

## Controls and observation

Build an xw_player_command with PLAY, PAUSE, NEXT, PREVIOUS or STEP_VOLUME (+1/-1)
and call xw_player_command. Check the negotiated provider.commands mask before
showing optional operations. SET_VOLUME is not bound by the original provider.
Zero-initialize each command, including when reusing storage. Only SET_VOLUME
and STEP_VOLUME use `value`; only PLAY_ITEM uses `item`, `container` and
`expected_revision`. Both direct and managed clients reject nonzero unused
fields before invoking a provider. A stale selection ID must not be silently
ignored by a later transport or volume command.

The managed-session example is `sdk/examples/player-managed-client/main.c`.
It accepts an explicitly delivered descriptor/generation, demonstrates snapshot,
event-based watch, media pages and explicit controls, and requests a close receipt
before local detach. See its README for invocation and validation boundaries.
It does not supply the still-unqualified original-manager grant integration.

For media queries, `container` is nonempty only for PLAYLIST_TRACKS. Clear it
when reusing a query for tracks, playlists or queue; an unrelated retained ID is
rejected before browsing. Failed or malformed pages leave both output rows and
page metadata unchanged. Treat those previous outputs as stale until a later
successful read; unchanged memory is not a fresh observation. A stale nonzero
revision requires rebuilding the application's view, not appending mixed pages.
The analysis host can advertise PLAY_ITEM after attaching its selection adapter;
this has not been installed or qualified on hardware. Supply item and leave
container empty. Pending validation returns BUSY/UNAVAILABLE; only explicit
command polling advances it, never a background automatic submission. A different
item or expected_revision starts fresh validation. After admission, another
explicit command is a new intent. Nonzero expected_revision must match a qualified
library revision; unknown revision0 cannot satisfy it. UNSUPPORTED is explicit.
ACCEPTED means the request was admitted to the original path, not that playback has
completed. UNCERTAIN must not cause automatic replay of a skip or other
non-idempotent operation.

The managed channel now preserves PLAY_ITEM IDs, optional container and full
expected_revision in its request ledger and advertises it only when supplied by
the backend. Native selection currently supports an empty container. Repeating
the same wire request ID returns its retained result, including BUSY; it does
not advance preparation. A new explicit xw_player_command call uses a new serial
and can advance a backend's documented pre-admission polling path. The SDK never
does this automatically and never retries ACCEPTED/UNCERTAIN on the caller's
behalf. Native selection and post-handoff lifetime still need hardware acceptance.

Confirm selection by observing the target ID and valid PLAYING state through the
normal snapshot/poll API. A preparation ticket or wrapper return cannot establish
playback completion. No new firmware or SDK archive is implied by this source change.

In the full firmware-research checkout, the offline cross-process selection fixture is:

```sh
python tools/test_player_broker_rpc.py --source
```

It uses the actual public client, IPC, broker, adapter and background validation
worker, with native media/GUI/playback boundaries modeled. It verifies pending
polls, exactly one submission and later target observation; it does not boot
SpiderApp or install a device endpoint.

The full checkout also provides tools/test_player_broker_system.py. It runs
separate ARM SDK-client and service processes using original Sony libc/socket/
LinuxThreads libraries in a generic ARM Linux guest. It verifies the combined
API/IPC/worker lifecycle with modeled player/media/GUI boundaries. The pinned
guest inputs are separate local research prerequisites, excluded from the SDK
source archive; this does not emulate Sony's complete hardware or firmware boot.

xw_player_snapshot reads state without changing notification history.
xw_player_poll compares observed snapshots and returns a changes mask for state,
track, metadata, volume and available library/queue revision fields. It is polling,
not a lossless event subscription. Read only fields present in snapshot.valid;
unknown state is not paused, and unavailable metadata is not an empty title.

Check the poll return code before reading either output. On failure the snapshot
and change mask stay unchanged, so previously displayed values are stale rather
than a fresh observation. A failed provider read invalidates poll history; the
next successful poll includes AVAILABLE and a full field refresh. Invalid
arguments and client reentry do not perform a provider read. A definite backend failure
also revokes the broker's metadata, browse/queue observations and pending
selection. BUSY remains transient and does not revoke selection/queue intent.
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
actual SDK service compiler and execute under ARM926 with original Sony libc.
The public-only consumer verifies modeled provider controls, polling changes,
bounded browse/revision atomicity, selection admission versus observed track
changes, unknown-state handling and cancellation/closed-state refusal. It checks
failed-observation output preservation and a full AVAILABLE/track/metadata
refresh after recovery without issuing any control command, and syntax-checks
the consumer/public declarations as C++.
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
