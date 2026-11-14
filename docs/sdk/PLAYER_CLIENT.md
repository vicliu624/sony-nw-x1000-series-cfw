# Original-player client

The experimental source SDK provides `player-client` and `player-managed-client`.
Neither module installs a backend or
starts a service. They control Sony's original player through an independently
supplied, authorized platform service.

`player-client` supplies bounded controls, snapshots and media pages.
`player-managed-client` adopts a manager-supplied descriptor and adds session
status, synchronized snapshots/events and confirmed end. It does not provide a
generic background-task manager. Read [lifecycle](LIFECYCLE.md) for the difference
between session end, local detach and system-task lifetime.

A Homebrew profile that suspends or finalizes SpiderApp cannot simultaneously
provide controls through its inactive owner. GUI ownership, grants and native
lifetime belong to the platform integration; applications cannot manufacture
them from an endpoint path. An absent service is an error.

Public modules contain no Sony fixed-address bindings, radio protocol, player
replacement or firmware installer. ABI structures are experimental source
contracts: rebuild consumers against matching headers; do not assume binary
layout compatibility across SDK versions.

## Build

A complete C consumer is provided at sdk/examples/player-client/main.c with
usage and integration notes in the adjacent README.md. It supports explicit
controls, bounded change polling and one-page track/playlist/member/queue reads.
It contains no radio protocol, state persistence or backend installer. The SDK
test builds it through the native-services compiler and runs --help with the
original Sony loader/libc; real endpoint behavior remains a separate check.
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
and STEP_VOLUME use `value`; SET_PLAY_MODE uses a canonical XW_MODE_* value.
Only PLAY_ITEM uses `item`, `container` and
`expected_revision`. Both direct and managed clients reject nonzero unused
fields before invoking a provider. A stale selection ID must not be silently
ignored by a later transport or volume command.

SDK alpha.11 appends SET_PLAY_MODE without changing existing operation numbers.
The canonical preferences are Normal, Repeat, Shuffle, Shuffle & Repeat and
Repeat One. Sony's native value mapping stays in the private platform adapter.
An accepted request means native admission and observed cached preference,
not engine completion or durable-save confirmation. Uncertain requests are
never automatically repeated.

Default ordinary and managed binds retain the original seven-bit HELLO, so
older applications can connect to a newer host. On a known matching new host,
`xw_managed_client_negotiate_commands(player, client, known_mask)` explicitly
requests newer capabilities. It changes only the local command bitmap after a
validated reply; the descriptor, grants, generation and observation history
remain owned by their existing lifecycles. A zero mask requests no commands.
Do not automatically probe legacy hosts or reconnect after negotiation failure.
This optional HELLO field expresses client knowledge and grants no authority.
The current ordinary bind has no explicit negotiation helper and therefore
continues advertising only legacy operations.

After successful managed negotiation, check the SET_PLAY_MODE bit, zero a
command, set `operation = XW_OP_SET_PLAY_MODE` and `value = XW_MODE_SHUFFLE`,
then call `xw_player_command`. The existing CONTROL grant and original-owner
checks still apply. Green selection in a controller must follow a fresh valid
mode observation, rather than changing when the request is sent.

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
playback completion.

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

## Verification

```sh
.venv/bin/python tools/test_firmware_regressions.py --suite sdk
```

The full checkout also has player core, broker, queue and original-instruction
tests. Source SDK archives can be checked in a clean extracted environment with
`tools/test_sdk_bundle.py`; `--player-only` checks only the ordinary player
consumer, not the entire SDK. All are PC-side checks with explicit modeled
native behavior, not physical playback or sleep/USB qualification.

Private original bindings are documented in [player integration](PLAYER.md).
Current hardware results are maintained in [status](../STATUS.md).
