# Original-player integration

The player integration controls and observes Sony's existing playback engine.
It does not decode audio in a second player. Public application use is described
in [player client](PLAYER_CLIENT.md); this guide covers the private platform
implementation for Japanese firmware 1.11.

## Supported surface and limits

| Capability | Implementation | Limit |
| --- | --- | --- |
| Play/pause, next/previous, volume | Owner-thread stock provider and bounded client transport | Current remote/session regressions remain open |
| State, current ID and volume | Copied CtrlInfo plus original GUI state | Unknown fields remain invalid; no speculative state |
| Title, artist and album | Native Moma reader, async cache and broker | Metadata is published only for the matching current ID |
| Stock tracks | Native bounded search and background reader | Database and provider lifetime must remain valid |
| Named containers/members | FORMAT3 hierarchy adapter | Do not equate every container with a qualified playlist |
| Current queue | Met-owner capture, immutable query copy and reader | Real grouped ordering and full runtime acceptance remain open |
| Arbitrary track selection | Experimental validation/source adapter | Not enabled by the standalone native command mask |
| Position/duration | Contract fields | Native units/validity are not qualified |
| Play mode | Matching private host/client extension | All five modes must be observed, not invented by the remote |
| Artwork | Current-ID native blob reader and bounded chunk transport | Complete Core2 display has not passed physical acceptance |

Published SDK source, a private analysis host and an installed firmware are
separate products. Source setup does not install a player service. The current
hardware acceptance table is in [status](../STATUS.md).

## Layers

| Source in `runtime/platform/player/` | Responsibility |
| --- | --- |
| `client.c`, `provider.h`, `player.h` | Typed commands, snapshots, validity and media pages |
| `rpc_*`, `managed_client*` | Bounded transport and supplied-descriptor managed client |
| `stock_info*`, `stock_state*`, `stock_engine_control*` | Verified original control/status bindings |
| `stock_media*`, `media_text*`, `id3_cover*` | Native objects, copied text and artwork |
| `metadata_async*`, `catalog_async*`, `queue_*` | Bounded background jobs and immutable copied inputs |
| `player_broker*` | Combine original state with matching metadata/media results |
| `managed*`, `host_managed_service*` | Grants, request correlation, events and generation drain |
| `host_handoff_bridge*`, `sleep_*`, `host_prepare_bridge*` | Application, sleep and permanent native transitions |

The original GUI owner dispatches controls and captures native identities.
Blocking metadata work uses an exclusively adopted background client. Radio
protocols and controller UI stay outside this layer.

## Image and ABI identity

The pinned stock SpiderApp SHA-256 is
`80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85`.
Rootfs/container identities are in [platform knowledge](../KNOWLEDGE.md).
Every private binding requires the matching image/profile; equal-looking
addresses in another Sony family are not compatible bindings.

Use the original ARM/OABI, libc, stat and fixed-layout time bridges. A modern
cross-compiler's time64 structures are not the stock ABI. Do not place modern
atomic-helper or pthread-layout assumptions into device code.

Fixed addresses belong only to reviewed platform adapters and composition
profiles. Give their roles names, retain code hashes and verify native calling
conventions. An exported string or decompiler function name alone does not
establish an externally callable API.

## Controls and observed state

PLAY and PAUSE must enter Sony's AudioC GUI state machine through request
`0x440027` from the qualified owner/stable state. Calling lower engine function
`0x27d6a0` directly can admit an engine ticket while leaving the GUI actor
unchanged. Published state requires both engine CtrlInfo and the GUI actor to
agree. Do not toggle a local state variable when a command is sent.

NEXT and PREVIOUS retain their reviewed direct adapter. Original software
requests `0x440028`/`0x440029` select next/previous handlers; corresponding engine
entries are `0x27dacc`/`0x27db98`. Admission tickets and completed playback are
different observations. Retrying an uncertain skip can skip twice.

Volume wrapper `0xb2630` delegates to `0x32a684` using initialized process state
and an internal mutex. It is not a standalone external-process getter. Its
adjacent setter's 30-step range does not authorize direct mixer/cache writes.

`stock_info.c` obtains an owned CtrlInfo clone through `0x27d4e4` and releases it
through `0x275f48`. Source lookup `0x27b5a4` retains the session and `0x27b7f8`
releases it after cloning. Missing sessions are not created. The 104-byte clone
contains scalar fields and retained track/chapter references; copied output must
outlive neither a borrowed pointer nor an unreleased original object.

The full research checkout keeps the private controller layout in
`runtime/platform/player/stock_controller_binding.h`. It defines the JP1.11 slot
at `0x6922d8` and the service/session words in its borrowed header. A stable
wrapper address does not prove that the same session is still
active. Status reads recheck both identities after releasing the owned clone.
Engine controls reject a replacement before submission as BUSY; a replacement
after submission is UNCERTAIN and must not trigger automatic replay. Unbinding
these adapters never closes Sony's original playback engine. Image and owner
checks remain required; the layout constants are not a standalone device API.

| CtrlInfo offset | Meaning |
| --- | --- |
| +4 | Primary target/state field |
| +8 | Substate |
| +12 | Error |
| +44 / +48 | Raw position/length inputs; units are not a public promise |
| +96 | Retained TrackInfo |
| +100 | Optional chapter, not the playback queue |

The GUI queue publisher at `0xa57f0` is not a general cross-thread API. Its
counter-based helpers do not grant an SDK worker GUI ownership. Owner-loop
integration, not direct calls from a remote worker, supplies control dispatch.

## Metadata and media identity

`stock_media_open` creates a client on the original GUI owner while its connection
token is valid. A worker adopts it before a read, including validation failures,
so cleanup can always occur on the correct thread. Close every completed or
cancelled job instead of retaining native clients across sleep/USB transitions.

Native connection token `0xab4f4` is also used by sequence factory `0x283830`.
A valid token type and nonnull manager are prerequisites, not lifetime leases.
Get-object entry `0x295ce8` returns an owned object; its metadata-set pointer is
borrowed. Do not dispose that set independently of its object.

The reader checks the returned canonical ID before publishing text. A different
object returns STALE, a missing one UNAVAILABLE. Supported local IDs use the
original local-object class at `0x60fc60`, domains 0/1 and MEDIA type. Canonical
hex formatting follows `0x28d64c`; unsupported domains are refused.

Native text length counts UTF-16 code units without NUL. Copy and validate text
before releasing the original object. Metadata merges only if the original
current-track identity still matches the requested job. Revision/epoch changes
discard the staged result; they must not relabel old metadata as current.

The task establishes worker ownership before invoking any domain callback.
Returning an argument error without a native call must still allow correct
client retirement. The original native dispose entry is void; software guard
failures and fixture-injected close faults must not be mistaken for a native
success/error return. An unconfirmed close retains the client, rejects new work
and prevents a drained result. Adopted clients stay on their worker for explicit
close retries; unadopted cancellation/startup failures remain with the creator.

There is one async metadata request slot and one background reader. New jobs
replace obsolete intents without publishing stale completion. Broker closure
waits for reader/client drain. An elapsed timeout does not free a still-running
native read or prove it cannot touch storage.

## Catalog, named containers and queue

The read-only catalog profile validates schema, not just numeric field names.
Original initializer `0x29d71c` maps property type 1 to `m<id>_id` and type 2 to
`u<id>`. Artist/album reference fields require the correct group, type and
storage tag; referenced members use `reference_id` and `child_index` for order.
Unknown profiles fail. Never open a database read-write to make a browse call
succeed or trigger a stock refresh from a read-only client.

Native FORMAT3 list search uses the original format condition and title sort.
Its child view validates canonical parent identity and FORMAT with typed enum
getter `0x2988f8` (kind 9), then uses CHILDINDEX ordering. An int32/uint32 getter
is not interchangeable. Missing format, non-3 format and corrupt type are
UNAVAILABLE, UNSUPPORTED and PROTOCOL respectively. No partial page is committed
on error.

Stock SWD resources `ucs2-dev-sid-239-00.swd` and `239-01.swd` map `tid.5` to
`tid-0501` (playlist) and `tid.6` to `tid-0446` (folder). Preserve zero padding.
Resource labels alone do not prove an active widget or its event path.

The current queue is the active Met sequence, not the catalog's row order. Capture
its session/revision on the Met owner. Background reads use copied query trees,
parent/domain identities, sort and physical ordinals. Reconstruction rejects
cycles, shared/orphan edges, incompatible scalars and overlapping buffers before
committing output. Do not pass live sequence/query pointers to database workers
or use an original helper that fills mutable sequence caches.

## Arbitrary-track selection

Do not expose PLAY_ITEM merely because an event accepts a numeric parameter.
Handlers for change-state 3/4 and payloads 100/-100 or 10/-10 are not arbitrary
media-ID playback. Source construction `0xacc9c` selects item/flat/grouped sequence
factories `0x283a38`/`0x283ad4`/`0x283bc4`, then calls controller `0x27d54c`.
Some wrapper results discard lower errors, so wrapper return is not acceptance.

The original descriptor copy at `0x4ab70` copies 64 bytes without cloning pointer
fields. Install `0xad270` and selected-ID setter `0xacb20` transfer the incoming
ID reference and dispose its predecessor. After handoff the caller cannot free
that ID just because a stop ticket failed. Source event `0x44001d` in the reviewed
stable handlers installs the descriptor and requests stop; subsequent `0x440104`
can construct it. Allocation, identity, ownership and admission must all be
tracked separately. No blind retry is safe here.

The experimental source adapter validates audio identity and stages an intent
with full-width revision before owner submission. It is analysis functionality,
not a qualified SDK arbitrary-track transaction on physical hardware.

## Artwork

The native object projection supplies the existing image blob. Dispatch
`0x299200`, full-file reader `0x293f2c` and thumbnail reader `0x293a90` translate
filesystem EOF `0x401` into Moma EOF `0x220f`. That specific result terminates a
valid image and retains bytes already returned; treating every nonzero return
as IO failure discards a complete cover. Genuine read errors fail that candidate.

Image dimensions, signature, size and current-track identity are validated.
The legacy `JPG` plus NUL envelope is normalized in RAM. An optional thumbnail's
wrong type, unsupported content or read error may fall back to the original full
image, releasing the prior clone and partial bytes. Allocation failures abort;
invalid backend counts are terminal PROTOCOL results. No source music is rewritten.
The separately guarded PIC/APIC UTF-16 alignment fix is described in
[artwork](../apps/REMOTE_ARTWORK.md).

Native blob success, authenticated transfer and Core2 decoding are three
independent acceptance steps. A source JPEG or a successful byte transfer is
not evidence of a visible remote cover.

Image reads start at offset zero. The managed READ session binds the broker's
cache epoch there; later chunks from a different epoch return STALE atomically.
Other readers keep independent bindings. The epoch is process-local and does
not change the IPC/radio format. A transient unknown track observation pauses
the controller's job; same-identity confirmation can resume it. Cache changes
restart from zero within a bounded budget instead of mixing image versions.
Typed reader BUSY and a new zero-offset I/O demand may retry after backoff.
Continuation reads do not restart failed jobs. Absence, unsupported and protocol
errors remain negatively cached.

## Lifecycle and verification

Use [lifecycle](LIFECYCLE.md) and [wireless](WIRELESS.md) for generation, close and
radio semantics. Original command 3 reaches library finalizers: revoke and drain
workers before finalization, not after observing source loss. Application command
6, sleep acknowledgement and USB exit have distinct adapters.

[Regression checks](../REGRESSION.md) provide the maintained entry point.
`test_stock_gui_host.py` executes the full native GUI state/request matrix.
Its `--engine-provider` profile separately checks provider PLAY/PAUSE routing;
it is not the full matrix. Both execute original GUI handlers with modeled
lower queue/audio effects.
`test_stock_media.py` executes original Moma/blob/filesystem paths with synthetic
provider storage. SDK tests build independent C/C++ clients and real local IPC.
Source intent/query/descriptor checks remain separate from physical playback.

Fixed profile addresses and digests are in the relevant C adapters and builder
receipts. Old receipts retain their hashes; code changes require new checks.
