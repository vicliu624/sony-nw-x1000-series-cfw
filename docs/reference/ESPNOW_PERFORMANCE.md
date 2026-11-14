# ESP-NOW performance contract

Target Japanese NW-X1050/NW-X1060 on Sony 1.11. Optimize the shared radio
backend before attributing end-to-end player behavior to RF limits.

## Acceptance target

The target is **1,000,000 useful application bits/s**, equal to 125,000 B/s or
122.07 KiB/s. The initial measured direction is X1060 to Core2, which carries
artwork. Reverse throughput is measured separately. PHY rate, submitted bytes,
MAC callbacks, duplicate frames, protocol headers and unvalidated packets do
not count as delivered application data.

The SDK-only benchmark must use the same shared owner, security and lifecycle
as the application. It must not query the player, decode artwork, write device
logs, depend on a router, use a separately qualified exclusive path, or generate
idle heartbeat traffic. Runs are explicitly requested, bounded, cancellable and
report receiver-validated unique payload bytes over a device-measured interval.
Use multiple payload sizes through the supported maximum; report fragmentation
and fallback behavior rather than hiding an oversized-packet slowdown.

Cover acceptance then repeats the same cached 131,872-byte image and checks
initial read delay, sustained transfer, final decode and display. At the target
rate its data alone takes about 1.055 seconds. This is a goal, not an achieved
result or a promise about the platform's physical ceiling.

## Established measurements

| Path | Result | Evidence scope |
| --- | --- | --- |
| Installed dev.34 + Core2 alpha.32 cover | 46.358 s normal drawing, 46.229 s without progress redraws; about 2.8 KiB/s | Physical cached-image trial; not a pure RF benchmark |
| Full BLK1 request/reply/completion | RX55 + TX71 + completion22 = 148 commands | Actual native backend with a synthetic register device |
| BLK2 read-vector version | RX12 + TX23 + completion6 = 41 commands | Same complete native path, host sanitizers and Sony-libc ARM926 |

The BLK2 command vector is fresh for each guard validation. Writes invalidate
it. Marker/address echoes, lease admission, packet-node identity and pre/post
RX tickets remain required. It is not a globally atomic SRAM snapshot: original
producer/consumer publication order and the operation's post-check still apply.

Client and owner FIFO framing no longer inserts a scheduled turn between an
available header and body. Each step performs at most two nonblocking reads,
checks HUP before both, and stops after one record or any partial I/O. Real-pipe
tests cover 1,470-byte records, absent bodies, short I/O, a writer disappearing
between header/body reads, output backpressure and staged-event retention.
The owner/service loops still have a 10 ms wait per turn; framing improvement
does not establish an event-driven loop or the throughput target.
The owner processes queued negotiation before admitting an application request
and checks readiness again afterward, with at most one RX event per turn.
Application readiness observed at turn entry cannot authorize a send after a
queued peer restart has changed the link.
An application RX is held in the existing receive buffer for one command
opportunity, then delivered before reading another RX. This preserves SEND
progress under continuous incoming data; stop clears the retained record.

## Current implementation limits

The 1,900-byte radio reservation is one removed original packet-pool block,
not the chip's total memory. The BLK2 code/state uses 1,888 bytes and retains
three large packet blocks. Another region cannot be used until original code
ownership and concurrent accesses are established.

Complete-frame transaction prototypes remain under ignored work/. Small-frame
submission can fit, but the supported maximum payload, staged allocation,
partial I/O, unknown submission, TX completion, RX consumption and stop must
all have explicit outcomes before such a profile replaces the existing path.
An unconfirmed side effect is never automatically repeated.

Current code does not explicitly configure a higher ESP-NOW peer rate. Record
actual TX/RX PHY information, then verify rates supported by both devices.
An application target of 1 Mbps requires PHY headroom for framing, ACKs and
contention; a 1 Mbps PHY setting alone cannot satisfy that payload target.
