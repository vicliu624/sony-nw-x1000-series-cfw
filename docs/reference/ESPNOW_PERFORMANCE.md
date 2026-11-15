# ESP-NOW performance contract

Target Japanese NW-X1050/NW-X1060 on Sony 1.11. Optimize the shared radio
backend before attributing end-to-end player behavior to RF limits.

## Acceptance target

The target is **100 KiB/s of useful application data**, equal to 102,400 B/s or
819.2 kbit/s. The initial measured direction is X1060 to Core2, which carries
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
rate its data alone takes about 1.288 seconds. This is a goal, not an achieved
result or a promise about the platform's physical ceiling.

## Established measurements

| Path | Result | Evidence scope |
| --- | --- | --- |
| Installed dev.34 + Core2 alpha.32 cover | 46.358 s normal drawing, 46.229 s without progress redraws; about 2.8 KiB/s | Physical cached-image trial; not a pure RF benchmark |
| Installed dev.37 FRM1 ioctl fix + Core2 alpha.32 cover | 149,975 bytes in 22.020 s, 6.65 KiB/s (54.5 kbit/s); 147 replies and zero timeouts | Physical X1060-to-Core2 run with normal drawing and a different cached image; measures application payload throughput |
| Continuous cover, 100 ms progress redraw | 85,474 bytes in 5.757 s, 14.50 KiB/s; 64 data replies, zero timeouts | Physical transfer with 52 full-screen draws during download |
| Continuous cover, progress redraw suppressed | 85,474 bytes in 3.715 s, 22.47 KiB/s; 64 data replies, zero timeouts | Same image and paired link. JPEG decode took 0.150 s after transfer |
| Full BLK1 request/reply/completion | RX55 + TX71 + completion22 = 148 commands | Actual native backend with a synthetic register device |
| BLK2 read-vector version | RX12 + TX23 + completion6 = 41 commands | Same complete native path, host sanitizers and Sony-libc ARM926 |
| FRM1 packet transactions | RX6 + TX1 + completion1 = 8 commands; a full 1,536-byte TX/RX pair uses 11 | Native host/ARM code connected to original MCU dispatch/allocator/submit/release instructions |

The dev.37 cover run averaged 142.2 ms from each request to its receive
callback, then 5.7 ms in the Core2 receive queue. Final decode took 0.292 s
after the transfer interval. The round trip includes the Walkman application,
its host-command path and both radio directions.

The release controller keeps the loading placeholder on screen until the
download finishes or fails. The two continuous-cover rows compare redraw
policies with the same firmware and cached image. The separate shared-link RAM
benchmark reached about 34 KiB/s at 1 Mbps PHY.

The opt-in `--radio-benchmark` builds of the Remote service, RF owner and Core2
add a console-only test. Run `rf-bench 256`, `rf-bench 1024`, or `rf-bench 1400`
on the paired Core2 after the shared Remote link is ready. The service submits
128 RAM blocks through the ordinary SDK client and stops producing new blocks
at its 20-second deadline. The test uses the same encrypted link and FRM1
driver calls as the Remote and bypasses player artwork lookup and chunk requests.
The Core2 reports unique validated payload bytes, receive timestamps and its
per-rate PHY counters. The X1060 reports elapsed sender time and wall time
inside submit, completion and other SD8686 `0x86` host commands. The ioctl time
includes driver, SDIO and firmware response waiting. Turn Wireless Remote off
to cancel through its existing shutdown path.

On Japanese NW-X1060 with the shared FRM1 benchmark image, Core2 received all
128 unique frames per run with no reported send failures. All 384 received
data frames used 1 Mbps with a long preamble (`sig_mode=0`, `rate=0x00`).
Throughput below divides verified bytes by the Core2 interval from the bench
request to the last unique data frame.

| Payload per frame | Transfer | Effective throughput | SD8686 `0x86` ioctl time / sender interval |
| --- | ---: | ---: | ---: |
| 256 B | 32 KiB in 13.633 s | 2.35 KiB/s | 1.481 / 13.650 s (10.8%) |
| 1,024 B | 128 KiB in 13.756 s | 9.30 KiB/s | 1.471 / 13.740 s (10.7%) |
| 1,400 B | 175 KiB in 14.974 s | 11.69 KiB/s | 1.873 / 14.960 s (12.5%) |

The 256 B and 1,024 B runs take almost the same time despite the larger frame
carrying four times more user data. At 1,024 B, submit, completion and other
host commands account for 301, 160 and 1,010 ms respectively. Increasing to
1,400 B takes two submit commands per frame. The sender still advances only
one in-flight operation, reading admission and completion on separate turns.
The Remote service and RF owner each sleep between turns. Sony `sys_poll`
(`0xc0096dcc`) rounds a 10 ms timeout to two 100 Hz ticks (`0xc0096e28..0xc0096e44`).
The comparison identifies a fixed per-frame cost on the shared software path.
It does not apportion the remainder to individual process wakeups or measure
actual channel occupancy and MAC waiting separately.

The readiness build retained the same Core2 binary, shared FRM1 image and
benchmark protocol. Each run again delivered 128 unique frames at 1 Mbps with
the long preamble, with no reported send failures.

| Payload per frame | Fixed waits | Readiness-based waits | Throughput ratio |
| --- | ---: | ---: | ---: |
| 256 B | 13.633 s / 2.35 KiB/s | 5.357 s / 5.97 KiB/s | 2.54× |
| 1,024 B | 13.756 s / 9.30 KiB/s | 8.087 s / 15.83 KiB/s | 1.70× |
| 1,400 B | 14.974 s / 11.69 KiB/s | 7.135 s / 24.53 KiB/s | 2.10× |

The 1,400 B run spent 1.574 of its 7.123 sender seconds in measured `0x86`
ioctls (22.1%). Each table entry is one run. The 1,024 B run took longer
than the 1,400 B run in this sample, so the relative results between payload
sizes do not establish a stable latency curve. The comparison does isolate a
substantial contribution from scheduling with the same negotiated PHY.

The phase timing profile keeps the same benchmark frame sizes and records the
service enqueue and completion times using the X1060 monotonic clock. The RF
owner also records dispatch, first submit, final submit return and completion
observations on that clock. Subtracting the matching owner spans from the
service's transmit interval gives the time from observed completion to service
receipt. The last pending ioctl entry and first completed ioctl return bound
the completion event after submit. Waiting before the first poll can overlap
actual transmission, so that interval is reported separately and cannot be
added to confirmed hardware waiting. Only runs with all frame timings and no
reported send failures support a complete split.

The phase timing build delivered 128 frames per run at 1 Mbps PHY with no
reported failures. The following intervals are mean milliseconds per frame.
Host and pipe time includes service work between sends, service to owner
delivery, owner preparation and the return of the completion to the service.
Submit through return covers all submit fragments. The final interval ends
when the owner receives the completed reply.

| Payload | Host and pipe | Submit | Submit return to observed completion | Before first check, included in preceding column | First check done |
| --- | ---: | ---: | ---: | ---: | ---: |
| 256 B | 11.52 | 2.37 | 19.51 | 18.56 | 128/128 |
| 1,024 B | 13.34 | 2.41 | 22.03 | 19.79 | 119/128 |
| 1,400 B | 13.81 | 3.88 | 24.31 | 22.47 | 122/128 |
| 1,400 B repeat | 13.98 | 3.79 | 24.93 | 22.36 | 119/128 |

For the two 1,400 B runs, about 33% of sender time is accounted for by host and
pipe intervals, 9% by submit and 58% by observing completion after submit. The
last pending observations give mean post-submit busy time lower bounds of
0.32 and 1.00 ms per frame for the two runs. Most frames are already complete
at the first check, so first-check scheduling is the next point to test. The
two measured rates, 32.47 and 31.91 KiB/s, describe these sessions with the
readiness scheduler and phase timing enabled.

The first-check variant retains readiness handling and uses a Sony `select`
timeout of one tick for the first completion wait of each submitted FRM1
application packet. The original kernel instruction replay gives one tick for
`select` with 10,000 microseconds and two ticks for `poll` with either 1 or 10 ms.
Later completion checks keep the existing timeout. Compare the observed first
check delay, total completion interval and ioctl count with the phase timing
results at the same PHY and payload sizes.

The one-tick first check delivered every frame at the same 1 Mbps PHY. The
1,400 B rows pool two runs on each side of the comparison.

| Payload | First check delay before / after | Submit to observed completion before / after | Completion ioctls before / after | Throughput before / after |
| --- | ---: | ---: | ---: | ---: |
| 256 B | 18.56 / 8.57 ms | 19.51 / 10.20 ms | 128 / 130 | 7.50 / 10.73 KiB/s |
| 1,024 B | 19.79 / 9.09 ms | 22.03 / 22.98 ms | 137 / 206 | 26.37 / 26.16 KiB/s |
| 1,400 B | 22.41 / 11.92 ms | 24.62 / 23.01 ms | 271 / 381 | 32.19 / 34.03 KiB/s |

The 1,400 B first-check completion count went from 241/256 to 134/256. The
earlier query mostly improves short frames. For larger frames, many of the
earlier queries return pending and trigger a two-tick retry.

The one-tick retry build also uses the shorter wait after a pending completion
for an in-flight FRM1 application packet. Both 128-frame runs delivered every
frame at the same measured 1 Mbps PHY. The 1,400 B baseline pools two runs for
throughput and averages the ioctl counts per 128 frames.

| Payload | Throughput before / after | Completion ioctls before / after | Total `0x86` ioctls before / after | Submit return to observed completion before / after |
| --- | ---: | ---: | ---: | ---: |
| 1,024 B | 26.16 / 21.51 KiB/s | 206 / 137 | 726 / 603 | 22.98 / 19.63 ms |
| 1,400 B | 34.03 / 34.14 KiB/s | 190.5 / 187 | 828 / 822 | 23.01 / 19.84 ms |

The completion interval fell by about 3 ms per frame in both runs. The 1,024 B
submit interval rose from 2.18 to 6.64 ms per frame, and total `0x86` ioctl wall
time rose from 1.075 to 2.171 seconds despite fewer ioctls. The 1,400 B throughput
was approximately level, within the spread of the two baseline runs. These are
comparisons between sessions, so the cause of the submit-time variation remains
unresolved.

The BLK2 command vector is fresh for each guard validation. Writes invalidate
it. Marker/address echoes, lease admission, packet-node identity and pre/post
RX tickets remain required. It is not a globally atomic SRAM snapshot: original
producer/consumer publication order and the operation's post-check still apply.

Client and owner FIFO framing no longer inserts a scheduled turn between an
available header and body. Each step performs at most two nonblocking reads,
checks HUP before both, and stops after one record or any partial I/O. Real-pipe
tests cover 1,470-byte records, absent bodies, short I/O, a writer disappearing
between header/body reads, output backpressure and staged-event retention.
The readiness build waits on the service pipes and stop socket and wakes the
owner for readable commands, writable output and native observer replies.
Local work that can advance runs immediately. Firmware receive and transmit
completion still use a bounded timer because the stock driver exposes no
waitable event for them. The owner continues to gate data and check stop and
retirement on every turn.
The owner processes queued negotiation before admitting an application request
and checks readiness again afterward, with at most one RX event per turn.
Application readiness observed at turn entry cannot authorize a send after a
queued peer restart has changed the link.
An application RX is held in the existing receive buffer for one command
opportunity, then delivered before reading another RX. This preserves SEND
progress under continuous incoming data; stop clears the retained record.

## Current implementation limits

The 1,900-byte radio reservation is one removed original packet-pool block,
not the chip's total memory. The release-safe BLK2 profile uses 1,884 bytes;
scalar uses 1,888 and BLK1 uses 1,896. The checked FRM1 profile uses
1,896 bytes with its RX counters and retains three large packet blocks.
Its 24-byte command entry occupies the replaced original command0x86 case at
0x88d8, within that case's 0x88d6..0x88f2 bounds. It does not reserve another
packet block. The complete case and all reservation code are fingerprinted.
Another region cannot be used until original code
ownership and concurrent accesses are established.

FRM1 is an explicit generated-image profile. It submits at most 1,464 frame-body
bytes per command; the full 1,536-byte protected body uses two fragments. TX
completion is separate. RX metadata, owned packet nodes and tickets are checked
before/after a staged copy and again around consumption. Too-small destinations
retain the packet; read failures publish no partial output. Plaintext and
protected APIs retain their existing application limits.

Data submission is never automatically repeated. A lost reply uses an absolute
ticket cancellation fence and readback: a fence that wins rejects late data;
a proven accepted TX remains tracked until original completion. The caller
receives UNCERTAIN and new data admission closes. Only verified resources drain.
Unresolved identity/lease/IO faults retain the unsafe hold. Repeated queue and
completion acknowledgements use the same idempotent absolute ticket and a
bounded check; they cannot consume the next packet or submit application data.
The private PC test bridges actual host/ARM native code to the exact MCU image,
including delayed commands, several lost replies, three occupied packet blocks
and original release ordering. IRQ/DMA, command-queue waiting, ciphertext
contents, actual SDIO timing and RF remain separate physical acceptance items.

Before original TX free, the full-radio profiles replace the pending aligned pointer with a
release claim. Only the callback that obtained that claim may publish completion.
A different task reusing the same freed packet address cannot overwrite the
status or acknowledge that send. A rejected queue cancels tracking before its
original free. Native reconciliation retains a pending claim until completion;
it never dereferences the old packet or treats its reuse as current ownership.
The preemption replay schedules this interleaving explicitly; it does not measure
hardware scheduling frequency or establish physical stability.

Current code does not explicitly configure a higher ESP-NOW peer rate. Record
actual TX/RX PHY information, then verify rates supported by both devices.
At 1 Mbps PHY, 100 KiB/s of payload would require 81.92% airtime efficiency
before accounting for host scheduling. The measured profile requires better
scheduling and a PHY-rate and airtime check before that target can be assessed.
