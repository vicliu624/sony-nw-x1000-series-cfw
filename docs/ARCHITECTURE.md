# Architecture

This project extends the userspace of the Japanese Sony NW-X1050 and NW-X1060
on firmware 1.11. Sony retains ownership of boot, firmware installation, device
drivers and the original playback engine. Extensions enter through verified
native bindings and expose bounded services to external applications.

## Responsibilities and dependencies

| Layer | Location | Responsibility |
| --- | --- | --- |
| Applications | `runtime/apps/<id>/` | Behavior, presentation, configuration, assets, version and application state |
| Public SDK | `sdk/include/x1000/`, `runtime/platform/sdk/` | Application-facing capability and lifecycle contracts |
| Service lifecycle | `runtime/platform/services/` | Grant and request identities, admission, cancellation and retirement |
| Player integration | `runtime/platform/player/` | Stock playback bindings, player state and dispatch on the Sony owner thread |
| Sony Settings adapters | `runtime/platform/sony-settings/` | Verified menu objects, callbacks and view layout |
| Wireless platform | `runtime/platform/wireless/`, `runtime/platform/espnow/` | Radio access, transport, lease ownership and restoration |
| Launcher and native adapters | `runtime/native/` | Package discovery, child processes, display, input and native ABI access |
| Shared storage and networking | `runtime/store/` | Package transactions, storage validation, verified libc bridges and network transport |
| Development tools | `tools/`, `scripts/` | Host-side builds, analysis, packaging and offline checks |

Platform adapters implement the capabilities behind the SDK. Applications
depend on those contracts. A shared implementation must be buildable without
an application's source, assets or build recipe. Move a helper into a shared
layer when it has an independent contract and a demonstrated use beyond the
application it came from. Keep the application's data formats, account policy
and presentation with the application.

Use the original libc for ordinary Linux operations. An SDK interface needs a
target ABI adaptation, a resource ownership contract or a reusable capability
with behavior of its own. Keep fixed Sony addresses, object layouts, stock
event IDs and image checks inside the native adapter that uses them. A private
system integration may connect services through verified native bindings.
Eligibility for that integration does not grant access through the public SDK.

Keep composition and behavior separate. Build tools select and validate
implementations. Runtime owners make policy decisions. A request being accepted
and the requested change being observed are distinct events. A renderer
displays the state supplied by the owner.

## Capability lifecycle

- The responsible platform owner grants access for a specific generation and
  scope. Match commands, results and completion events against that identity.
- Stop admitting new work before draining requests and releasing resources.
  Admission stays closed through pending or failed cleanup. A new session
  requires a new grant.
- Cancellation revokes the affected continuation. Resources already committed
  to cleanup still retire under their original owner. A later valid context
  cannot revive a canceled continuation.
- Match native exit requests to their own epoch and verify their native context
  before delegation. The service generation identifies service retirement
  within that transition.
- Preserve uncertainty as a distinct result. An unverified close, timeout or
  child exit does not establish that all resources were restored.
- Dispatch native work on the qualified Sony owner thread. Use its event and
  descriptor readiness to drive asynchronous work. Avoid idle polling.

See the [SDK lifecycle contracts](sdk/LIFECYCLE.md) for the application-facing
rules and [stock lifecycle bindings](reference/STOCK_LIFECYCLE.md) for the native
call paths.

## Original application switching

Sony owns application switching, sleep and shutdown. Defer an original
continuation while extension-owned resources are still retiring. Forward it once
the relevant drain and native owner checks pass. A completion event comes from
the original flow and must match the pending transition.

| Transition | Extension obligation |
| --- | --- |
| Application switch with a retained native process | Retire player-dependent consumers and preserve the verified native connection |
| Return to the player | Reopen admission after newer, successful native activation |
| Sleep | Retire custom consumers before acknowledgement and follow the stock sleep and wake path |
| USB or permanent exit | Verify retirement before delegating shutdown and storage ownership transfer |

Qualify each transition independently. Each has its own native inputs, resource
obligations and completion evidence.

## Radio and player ownership

The serialized system owner controls the radio. Native Wi-Fi retains ownership
of its stock connection. A shared consumer receives a scoped borrow and may
release that borrow using its matching identity. Ownership of the connection
remains with the native owner.

Radio transport and player control are independent capabilities. A consumer
that needs both acquires each with the required scope. Departure from the
player retires the consumer's player-dependent work without extending its
authority over radio, sleep or USB.

Require matching retirement evidence from the owner of a resource before
releasing its lease. Failure keeps that resource in cleanup under the same
authority. Preserve binding keys and monotonic packet counters across updates.
Counter recovery follows the security contract for the key that owns them.

See the [wireless contract](sdk/WIRELESS.md) for mode, ownership and shutdown.

## State and storage

- Keep each application's executable, metadata, assets and state with the
  application. Store persistent application data on the qualified exposed user
  volume. Check mount, device identity, link traversal, available space and USB
  ownership before access.
- Keep player observations, presentation state and transfer buffers bounded in
  memory. Mark cached observations and bind chunks to the identity and epoch of
  the source that produced them.
- A diagnostic result records the failed operation and its original result code.
  Tie parent and child results to the build, process, request and assigned
  generation before attributing them to one attempt.
- Diagnostic writes use a fixed user-storage budget and occur after the required
  ownership and quiescence checks. A record checksum establishes integrity.
  Attempt identity establishes attribution. Missing evidence remains unknown.

See [diagnostic replay](REGRESSION.md#groups) and [current observations](STATUS.md)
for available evidence and test limits.

## Build and review boundaries

Build tools accept explicit inputs and produce reusable, hash-checked receipts.
Keep compile-time requirements separate from the identities selected for
deployment. Reuse a verified component when its actual inputs and compile
contract match. Review the deployed files and their launch-time relationships
together.

Run the smallest verification scope that covers the affected contracts.
Independent checks consume construction helpers or reviewed artifacts. Keep
release qualification tied to the exact composition that was tested. Preserve
original inputs, usable rollback packages and failure evidence.

Use [the engineering workflow](WORKFLOW.md) for scope and [the build guide](BUILD.md)
for commands, artifacts and package review.

## Developer delivery constraints

A new app can be created, previewed and packaged through the documented SDK.
Applications declare the modules they need and receive a clear result when a
capability or storage grant is unavailable. Public interfaces specify who owns
the resource, when access begins, how work stops and what makes reuse safe.

The SDK archive carries its public source and examples. Caller-level tests cover
failure and cancellation. A physical acceptance claim requires exercise of the
exact build on the device through each affected startup, application return,
sleep, USB, RF or audio path. See [current status](STATUS.md) for qualification
and the [developer guide](APP_DEVELOPMENT.md) for the supported application flow.
