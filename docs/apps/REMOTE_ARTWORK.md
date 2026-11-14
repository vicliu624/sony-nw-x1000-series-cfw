# Remote artwork and the original PIC/APIC parser

The original parser fix, native image reader, authenticated transfer and Core2
decoder are separate parts of artwork support. The fix does not replace the
audio decoder/DSP or rewrite music. Physical cover display remains unresolved;
see the current status table.

## Original UTF-16 alignment defect

The pinned Japanese 1.11 SpiderApp parser at `0x312f0c` locates PIC/APIC image
data after the picture description. Its UTF-16 branches scanned for a two-zero
terminator one byte at a time. With a nonempty UTF-16LE description ending in
an ASCII character, the character's high zero byte and the first terminator
byte form a false match. The returned image starts one byte too early.

Existing native blobs may carry `JPG 00 FF D8 FF` after the parser fix.
The reader normalizes only that exact JPG envelope and the corresponding PNG
signature in RAM; it does not scan away arbitrary leading bytes. Unsupported
thumbnail content releases its cloned blob and tries COVERART/ALBUMCOVERART.
The controller bounds initial UNAVAILABLE retries to five and records
result/reply/timeout counters separately from sprite allocation.

An actual source track uses ID3v2.3, UTF-16 description `Front cover`, and an
85,474-byte baseline RGB JPEG at 800x800. The original parser reads image offset
374; the real JPEG starts at375. Its format-prefixed output begins
`JPG 00 FF D8`, rather than `JPG FF D8 FF`. This is independent of progressive
JPEG support or image resizing.

`tools/stock_artwork_fix.py` guards and changes three ARM instructions:

| Address | Original | Replacement | Scope |
| --- | --- | --- | --- |
| `0x3139cc` | `add r2,r2,#1` | `add r2,r2,#2` | APIC UTF-16 description |
| `0x313b00` | `add r1,r1,#1` | `add r1,r1,#2` | PIC UTF-16 byte count |
| `0x313b08` | `add r2,r2,#1` | `add r2,r2,#2` | PIC UTF-16 pointer |

Each instruction remains four bytes. ASCII scanning, native media interfaces,
ELF layout and audio paths remain unchanged. The builder's explicit
`--stock-artwork-fix` composes this before Settings count and native-page profiles, so profile
hashes describe the final combined image. Unexpected or already-patched source
instructions are refused.

`tools/test_stock_apic.py` executes the original parser with original file bytes;
only its file callback and memcpy boundary are supplied. It checks both PIC
and APIC, Latin-1, UTF-16LE/BE and empty descriptions, with and without the fix.
Optional `--source`, `--library` or `--file-list` inputs enable local read-only
replay. Private tags/reports belong in ignored work. Windows names that exceed
Linux's UTF-8 component limit can be read on Windows and exported as short-name
tag-only local test inputs; this does not require changing the library.

The local83-track corpus contains81 embedded pictures. Original parser replay
produced incorrect bytes for58; the patched parser reproduced all81 original
pictures exactly. Two tracks have no embedded picture. This proves extraction
for those inputs, not native catalog discovery, cache invalidation, decoder
acceptance or physical Sony display. No corpus files were rewritten.

## On-demand remote transport

Changed-state sampling precedes construction of the next image reply. The
sender/worker fixture submits a new image request before the prior TX completion
and checks that a changed volume is sent before another chunk. Previous ordering
starved this update. There are no idle heartbeat packets in the current version.

Read retries retain their session/request/track/offset identity, allowing a valid
late reply in the retry gap. A different identity cannot enter assembly. Controls
are not retransmitted. Successful chunks admit the next read without a fixed
timer; one outstanding request provides flow control and frontend input has
priority. The first valid total size admits a fixed size-based job budget,
bounded by ten minutes from job start; BUSY and retry traffic do not renew it.
Completed/failed images do not create indefinite background traffic. Offline
revocation retains byte counters for diagnosis without allowing late assembly.

A live same-session snapshot without a valid track ID pauses the image job.
It does not erase received bytes or restart its deadline. New requests,
late-chunk acceptance and presentation are blocked until the same identity is
confirmed. A different track/session or revoked connection invalidates the job.
The frontend applies observations before processing later queued image replies,
so a reply cannot append against an identity already marked unknown.

The client owns request, timeout and retry state. Renderers consume a const
progress view and an image-ready predicate; they do not edit counters. Local
send refusal retries the same read identity with a bounded budget. Explicit
user retry keeps serials monotonic and requires a confirmed current track.

The native read result is not POSIX read: file-blob293f2c and thumbnail-blob293a90
map PLT_FS_EOF0x401 to MOMA_EOF0x220f. The adapter accepts that specific terminal
result, retains any bytes returned with it and stops reading. Other errors,
oversized counts and the total-length bound remain enforced. Treating all
nonzero results as errors discarded a valid image at EOF. The original blob
and filesystem adapter now execute in the regression down to a modeled read
syscall, including EOF and a genuine error. The former zero-at-EOF synthetic
blob callback is retained only for its own explicitly modeled cases.

`tools/test_stock_media.py --cover-only --cover-image <private JPEG>` can replay
an actual locally extracted picture. The Back To Black85474-byte JPEG passes
byte-exact native file-blob/EOF replay. The authenticated sender/client suite
separately assembles an85474-byte payload in1024-byte chunks. Source projection
and the read syscall remain fixtures; these are not physical display evidence.

Candidate isolation also replays the original file reader with thumbnail I/O
failure followed by a healthy full-cover blob. It must reproduce the same
85,474-byte image exactly and release both clones. The optional
`tools/check_core2_jpeg.py --decoder-dir <local M5GFX src/lgfx/utility> --image <JPEG>`
check in the full research checkout uses the unchanged local decoder, its
3,900-byte pool and the current 96-pixel fit/division choice. That source image
decodes successfully to 10,000 intermediate pixels before the final affine
sprite conversion. The decoder source hashes are recorded. This codec-only check
does not exercise final drawing.

The optional full-checkout `tools/check_core2_sprite.py --m5gfx-src <local src>
--image <JPEG/PNG>` calls the same `core2/src/cover_renderer.h` as the frontend.
It uses software M5Canvas buffers and the unchanged local M5GFX 0.2.32 sources.
Synthetic JPEG/PNG, fit/letterboxing, rejection, repeated draws and all 9,216
copied RGB565 pixels are checked, as is the surrounding parent buffer. A local
85474-byte source JPEG passes this software path. Inputs are hashed before build
and checked again after execution. Physical LCD, PSRAM, transfer timing and complete
cover display remain unqualified.

The stock Moma registry identifies THUMBNAIL16, COVERART17 and ALBUMCOVERART18
as blob attributes. These are not database schema IDs. A dedicated background
worker requests these attributes for the current opaque media ID, verifies the
returned identity, clones/reads/disposes the native blob and closes its native
client per job. It prefers the thumbnail and strips an optional native
three-byte JPG/PNG type prefix before publishing compressed bytes.

An optional candidate's wrong type (`0x2203`), unsupported content or read I/O
failure cannot hide a later usable cover. The reader disposes the failed clone
before trying the next attribute and discards its partial bytes. If no candidate
succeeds, an observed I/O failure remains I/O rather than becoming absence.
Clone allocation failures abort the lookup; malformed byte counts are PROTOCOL
and size violations remain terminal. No bound is relaxed. The original UI's
`0x42680`/`0x42704` paths separately confirm ALBUMCOVERART-to-COVERART fallback.

Reader BUSY is transient. An explicit zero-offset demand can also retry I/O
after the existing one-second backoff. Continuation chunks cannot restart a
failed native read. Absence, unsupported and protocol results stay negatively
cached. There is no autonomous source scan, timer thread or periodic refetch.

The broker allocates one bounded512KiB RAM buffer lazily on the first artwork
request. It caches one successful image per track/revision and serves1024-byte chunks.
No image, partial file or cache is written to /tmp, /db, /var or user storage.
Track/source changes revoke cached output. Existing worker stop/drain rules
apply before broker destruction, application handoff and native sleep; an
unfinished worker is never reported as retired. The buffer is freed on close.

Private managed control6 requires an active READ grant and post-call epoch
validation. It returns track ID, total length, offset and bytes, never a native
pointer or arbitrary filesystem path. Old control operations retain their
framing. The matching service/host must be packaged together; this private
extension is not automatically advertised to arbitrary older hosts.

Read offset zero first. The local managed READ session binds that first chunk
to the broker's immutable cache epoch. Later chunks from another epoch return
STALE without changing caller output; another reader cannot replace this grant's
binding. The epoch stays inside the player process and changes no radio or IPC
frame layout. A client may restart the image read at zero at most twice within
its original job deadline; it never appends a new cache to an old partial image.

Authenticated WRAQ/WRAR frames bind each request/reply to session, request,
opaque track ID and offset. A reply is at most1137 bytes. Playback receipts,
session recovery and library replies precede queued artwork. New artwork reads
are deferred during the short post-command settling interval. Corrupt, stale,
wrong-track and wrong-offset chunks cannot enter the image assembly.

Core2 allocates compressed storage in PSRAM and decodes an image once into a
96x96 RGB565 PSRAM sprite. Dimension parsing gates images to at most2048x2048;
the existing M5GFX JPEG/PNG decoder still decides actual format acceptance.
Subsequent UI redraws copy cached pixels. Missing, malformed, oversized or
timed-out artwork uses the placeholder. Nothing is periodically retransmitted
after a completed or failed fetch for the same track/session. The Core2 card
displays progress; tapping a failed image explicitly starts a new bounded read.

`id3_cover.c` is a separate bounded portable extraction component, tested under
host sanitizers and the original Sony libc/ARM926. It is not currently linked
into the production native lookup: the active integration retains Moma and
fixes Sony's parser, instead of introducing a second persistent music scanner.

## GUI progress and screen-off boundary

The radio owner still requires fresh mode observations. A display-idle select
timeout longer than this lease cannot support owner-thread IPC progress.
The remote scope uses the pinned original getter/setter to bound GUI idle to
200ms, with a20ms burst while artwork requests progress. The burst expires
after one second without further progress. It does not send more status,
generate input, change the display timeout or defeat native system suspend.
Off/handoff restores only the exact timeout still owned by this scope; later
Sony policy changes take precedence. The original setter returns the previous
timeout, not a zero success code. Original instruction replay covers clamp,
burst, restoration, policy replacement, wrong owner and changed image.

Diagnostic capture covers STARTING and active service phases. It records
readiness/retirement, native context loss, sleep preparation and GUI timeout
bounding in bounded RAM while custom children are live. A quiescent flush uses
one preallocated 2 KiB user-volume snapshot and fsync, after activation and child
retirement checks. There is no growing logger, system-path fallback or filesystem
write from the active observer poll. This diagnostic policy is separate from
fixing the reported screen-off disconnect.
