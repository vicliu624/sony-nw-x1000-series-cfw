# Service lifecycle

System capabilities require explicit ownership, admission and completed cleanup.
A public header, a connected socket or a running helper does not establish any
of those conditions. This contract applies to player control and radio transport
independently; Wireless Remote combines them without merging their authorities.

## Available interfaces

| Interface | Availability | Responsibility |
| --- | --- | --- |
| Callback application runtime | Public SDK | One foreground app, input/render callbacks, close handling |
| Native service modules | Public source SDK | Explicit C APIs with app-owned loops and module-specific cleanup |
| `player-client` | Experimental SDK source | Bounded controls, snapshots and media calls to a separately supplied service |
| `player-managed-client` | Unreleased SDK source | Adopt an authorized descriptor, inspect/sync/end that player session |
| Session/request/event core | Private platform | Owner-side grants, epochs, retained outcomes and bounded event history |
| Native remote task factory | Private firmware integration | Coordinate the Settings consumer and actual original lifecycle |
| Generic app background-task manager | Not provided | Apps cannot register arbitrary persistent system tasks |

Source version and publication are separate. Read [SDK quick start](README.md)
and [player client](PLAYER_CLIENT.md) for the supported build surface. Do not
copy private Settings callbacks or construct an app-local global authority.

## Connection, session and task

A connection is an IPC transport. A session is a provider grant with a generation
and lifetime. A system task is an operation that may outlive the page that started
it. Closing a Settings page is not a request to stop an explicitly enabled task;
closing a socket is not proof that hardware has been released.

A provider authenticates the caller and supplies a capability; self-reported app
names, PIDs, file paths and task IDs are not authority. A consumer cannot grant
itself permission by filling a session structure. The private native factory is
responsible for the descriptor and grant it passes to a child.

## Session core

The private `runtime/platform/services/session.[ch]` core is serialized on its
owner thread. It has four live slots and four retained successful close receipts.
A handle contains generation and serial. Restart must use a fresh nonzero
generation; old handles never become valid again.

Current session states are EMPTY, ACTIVE, CLOSING, CLOSED and FAILED. Reasons are
CLIENT_CLOSE, CLIENT_LOST, HOME, USB, SLEEP and SOURCE_LOST. These enums describe
reported semantics; they do not prove every native path is connected or tested.

| Operation | Required behavior |
| --- | --- |
| Open | Request only supported, independently authorized grants |
| Admit | Require matching generation/session and current capability |
| Stop admission | Deny new operations while preserving cleanup access |
| Revoke | Record reason and invalidate operation epochs |
| Close step | Return pending until owned work is drained and released |
| Close query | Report live close state or an available retained receipt |
| Resume admission | Trusted provider revalidates native resources first; old handles stay invalid |

READ, CONTROL and BROWSE grants are distinct. A result staged by a backend is
committed only after a post-call epoch/grant check. Revocation during a read
therefore cannot publish its data as a current result.

Quiescing the manager does not perform provider cleanup. A session drained result
does not establish hardware off. The owner must drain actual readers, queued
work and adapters before acknowledging a native transition.

## Requests and uncertainty

Every side-effecting intent has an identity scoped to its live generation and
session. Duplicate identities return the retained outcome, including BUSY or
UNCERTAIN, instead of executing again. The same identity with different content
is rejected. A new explicit intent requires a new identity.

OK, ACCEPTED, BUSY, PENDING and UNCERTAIN are distinct domain results. ACCEPTED
means admitted, not audible playback. BUSY means no new effect was admitted.
UNCERTAIN means the effect/outcome cannot be established. A timeout is not a
cancellation receipt and must not automatically retry NEXT, PREVIOUS or another
side effect. Exactly-once execution across crashes is not promised.

Events use a bounded sequence history, not a lossless hardware log. A missing
history range requires explicit resynchronization. Snapshot and sequence must
be captured together. Reading one session must not consume another's cursor.

## Managed player client

`xw_managed_client_bind_stock` adopts a manager-supplied connected descriptor,
expected generation, timeout and cancellation pointer. It starts no service and
has no automatic reconnect. Use fresh zeroed static/heap objects and serialize
calls from a worker; these contexts contain substantial bounded scratch storage.

Status, sync and events observe the granted session. Player-domain calls require
the corresponding grants. Optional play-mode/artwork extensions require matching
host support; do not probe unqualified legacy hosts automatically.

`xw_managed_client_end` requests and confirms server-side session close.
`xw_player_close` then detaches local client resources. Detach alone does not stop
or confirm cleanup of a server-owned task. A failed exchange does not count as a
successful end receipt. No native pointers or stock entry addresses belong in
application IPC messages.

The optional artwork stream binds a private cache epoch per READ grant after
its zero-offset chunk. Cache replacement returns STALE before committing later
chunks. Revocation during the provider read discards both staged data and its
epoch. Image buffers contain copied bytes, not retained native handles; missing
observation and confirmed session revocation have different client transitions.

## Original lifecycle integration

The GUI owner pumps bounded service work and native transitions. A helper may
perform a blocking read only through an exclusively adopted job client, with
explicit drain/join before stock finalization. Do not wait for a worker from a
callback that the worker needs in order to finish.

Closing admission does not remove that progress requirement. The private remote
factory retains its bounded GUI wait while children/readers or retirement remain
outstanding, including during native exit. It restores the previous native wait
only after cleanup. This changes local scheduling, not wireless traffic or the
conditions required for Sony's acknowledgement.

The background task owns media-client acquisition, adoption and retirement.
Domain callbacks borrow an already adopted client; they may reject input without
calling a native reader and must not dispose that client. Failed thread startup
and cancellation before adoption are cleaned by the original owner. After
adoption, only that worker retries a failed close, on an explicit owner stop
request. A failed close retains its record and blocks new jobs.

A successful read is not published when closing its client fails. Drained means
stop was requested, the thread exited, no media client remains and no cleanup
error is outstanding. Neither an exit flag alone nor clearing a pointer can
establish this result. Cleanup retries preserve the native thread context and
do not add a timer, forced kill or a new persistent service.

The private player broker stops admission on its first close attempt, before
closing any attached provider. A pending or failed release retains the context
for more close steps; it does not admit playback commands, snapshots, library
reads, artwork allocation or new provider attachments. Normal ticks do not
restart work during this interval. Only successful close followed by a fresh
bind reopens admission, without closing the borrowed original player.

Application handoff, sleep and permanent exit use separate adapters:

- Application command 6 drains player-dependent custom work, retains ordinary
  Wi-Fi and then forwards the original coordinator. Matching native activation
  and a newer client sequence permit player admission again.
- Sleep preparation waits for custom drain and qualified radio retirement before
  stock acknowledgement. Recovery verifies the native state and matching epoch.
- USB/permanent preparation stops admission, drains owned work and follows stock
  shutdown. It cannot rearm through an application-return callback.

Screen blanking alone is not completed sleep. A native pending token is not a
cleanup receipt. Preserve original callback results, thread affinity and ABI.
Detailed radio rules are in [wireless lifecycle](WIRELESS.md).

## Background consumer cleanup

The native Settings factory owns a remote task independently of the page.
Its app-local worker observes stop requests between data stages, including
after an optional producer callback. Accepted stop closes data admission before
starting player/radio cleanup. In-flight calls may finish; their late errors
remain visible without replacing the first accepted stop reason. A signal flag
stops data production while cleanup RPC remains available. This private worker
contract is separate from the unreleased general background-task interface.

Starting it returns readiness only after both player and radio setup succeed;
Starting and On are different states. Stopping it waits for service/owner
retirement and original-player SDK drain. Native page closure does not orphan
an unmanaged child or create a duplicate owner.

An uncertain child exit retains fault handling. Only a typed startup refusal
with independent, matching cleanup evidence permits a clean retry. A closed
proxy reader cannot replace the RF owner's receipt. Temporary logs, keys,
counters and task state stay on qualified user storage, never system-backed
`/tmp` or an unverified fallback.

## Verification and limits

[Regression checks](../REGRESSION.md) exercise public SDK consumers, local IPC,
request deduplication and independent native lifecycle paths. Tests of the
session core use supplied authority/cleanup adapters. Tests of original ARM
callbacks use modeled devices. Neither establishes actual Sony scheduling,
RF power, audio, sleep/wake or USB recovery.

The public SDK does not yet offer a general manager-delivered background-task
API. Keep private factory functions private until their complete lifetime,
error and cleanup contract is part of a qualified public implementation.
