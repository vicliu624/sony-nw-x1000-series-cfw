# SDK API1 reference

Headers: sdk/include/x1000/app.h and storage.h. New C/C++ applications call the C
facade; current declarative recipes compile application-local .c files. C++ can
include the headers, but C++ toolchain/runtime recipes are outside this profile.

## Lifecycle

Define one const xw_program named xw_application. Fields: api (XW_API_VERSION),
stable id, title, state_bytes (at most65536), init, event, draw and finish.
The SDK allocates zeroed state. draw is required; other callbacks are optional.
init/event/finish return zero on success. The entry source provides main and
safe --help/--version/--selftest flags without device or storage access. The
device accepts no --preview, --data or host render paths.

init runs after the display backend opens. finish runs once whenever init was
entered, including failed init. It does not run if display setup failed before
init; the backend still closes its partial resources. Finish and backend-close
errors produce nonzero exit status, including during cancellation. A failed
event/draw presentation stops the loop; there is no automatic success fallback.

| Function | Contract |
| --- | --- |
| xw_request_exit(app) | Request bounded loop exit; no signal-handler cleanup |
| xw_redraw(app) | Mark the canvas dirty; next loop calls draw and present |
| xw_is_stopping(app) | Check normal exit or the native signal token immediately, including inside callbacks |
| xw_is_preview(app) | Informational PC flag; never an ownership proof |
| xw_sdk_version() | Build's pinned SDK version |

xw_event contains type, x/y, elapsed_ms and stop reason. Types: TICK,
TOUCH_DOWN/MOVE/UP and STOP. Coordinates are logical240x432; out-of-bounds touch
is reported as -1/-1. Native elapsed time uses the existing verified OABI
CLOCK_MONOTONIC adapter; maximum reported delta is1000ms. Time can accompany
touch events as well as ticks. Callbacks must poll/return promptly; the SDK cannot
preempt a blocking third-party decoder or guarantee cleanup after SIGKILL.

The existing launcher retains HOME observation and signals the child process
group. SDK apps do not race it by opening the same HOME event stream. SIGTERM
and SIGINT request stop through the normal loop; prior handlers are restored.
Native stop reason is SIGNAL because the launcher does not forward a reason
message. Host replay can explicitly model HOME and USB, which is not proof of
physical handoff. Returning from main alone does not qualify Sony restoration.

## Canvas and input

Logical surface is240x432 RGB565. xw_rgb clamps8-bit channels; xw_fill and
xw_image clip all writes to the current clip and surface. xw_clear respects the
current clip. xw_clip replaces the clip; xw_reset_clip restores the full surface.
Negative/empty rectangles draw nothing. No GPU, framebuffer ownership or model
independence is implied by these pure drawing functions.

xw_text renders printable ASCII through the maintained proportional Noto16px
raster, scales1..4, with alpha blending. Unsupported bytes return an error
before drawing. xw_image accepts a caller-owned RGB565 array, exact count and
optional transparent key; dimensions are bounded to4096. It does not decode PNG
on the player. Resource conversion can be done with PC tools; keep external
decoders/resources explicitly versioned and licensed.

xw_button_event accepts zero-initialized per-button state, a rectangle and an
event. It fires on release inside the initial button, cancels drags exceeding12px
and resets on STOP. xw_button_draw provides a simple label/button presentation;
application-specific drawing can use the same event helper.

## Data and resources

xw_data_read/write operate on pre-existing HOMEBREW/data/<id>. No system fallback
exists. Names have1..64 ASCII letters/digits/dot/underscore/hyphen, cannot begin
or end with dot and cannot contain separators. Data size is at most65536 bytes;
reads report size separately and reject a larger file rather than truncate it.
xw_resource_read reads flat files under installed assets/, at most1MiB. Put such
files in application-local resources/ to have the builder copy them into assets/.
Font and SDK license notices are copied automatically.

All native IO is gated by xw_storage_set_owner's callback. It must return1 only
while qualified original-platform coordination establishes player ownership;
zero and errors deny IO. The default native provider denies IO. Host preview
uses only its explicitly selected isolated --data directory and optionally uses
a test callback to simulate denial. This is file confinement by contract, not an
OS sandbox; a native C program can bypass the facade if its author chooses.

Checks include the pinned vfat user mount source, separate root device,
directory descriptor/path identity, symlinks, hardlinks, regular files,
cancellation, bounded sizes and a1MiB free reserve for writes. The initial
volume observer is reused from the maintained QQ storage implementation as a
private source dependency, not a public QQ API. Existing source layout is kept.

| Result | Meaning |
| --- | --- |
| OK (0) | Complete operation |
| MISSING (1) | Data file does not exist |
| INVALID (-1) | Invalid name, size or arguments |
| OWNERSHIP (-2) | Busy/unknown USB or storage ownership |
| BOUNDARY (-3) | Mount, path, identity, link or pending-temp failure |
| SPACE (-4) | Free space/reserve cannot be established |
| IO (-5) | File operation failed |
| UNCERTAIN (-6) | Rename occurred; durability or subsequent ownership is uncertain |
| STOPPED (-7) | Cancellation/exit prohibits further IO |

Writes retain the old file until the new file is synced and renamed. An existing
.sdk-write.tmp is not silently overwritten or removed. Ownership loss stops
cleanup writes and may leave that temporary file; inspect/recover it explicitly
under established exclusive ownership. UNCERTAIN must not be treated as a safe
automatic retry. Settings should be written during a live event, not in finish,
because stop state prohibits new persistent operations.

## Build modules

build.json pins the exact SDK version and selects app/canvas with optional
storage. Omitting storage excludes its implementation and private filesystem/
volume dependencies from both host and ARM builds. Calling a storage function
then fails at link time; include the module when such a function is required.
Unknown or duplicate modules are rejected. The source SDK bundle includes both
profiles so a developer can make this choice without replacing the runtime.

## Compatibility policy

Source API1 and exact SDK version are recorded separately from app and firmware
versions. Static adaptation avoids a player-wide shared-library upgrade. Future
facade breaks require an SDK major version; experimental fixes still require an
explicit SDK pin update. Existing app.ini API1 and package formats are preserved.
The callback facade above does not expose network/PCM/FM entry points. SDK0.2
adds separate [native services](SERVICES.md) for existing custom-main apps,
preserving their own buffers, policies and interface semantics. Raw flash,
NVP and arbitrary wireless-radio interfaces remain outside the SDK.
