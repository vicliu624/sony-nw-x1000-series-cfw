# ESP-NOW on the NW-X1000: mechanism and limits

Target: the Japanese NW-X1060 on the1.11 platform. This describes the XNOW
implementation whose identified native worker passed a physical bidirectional
test with an original Cardputer. Other devices, firmware revisions and newly
compiled payloads require independent checks.

## What has actually been implemented?

The over-air traffic is ESP-NOW-compatible unencrypted v1 vendor-specific
Action traffic, transmitted directly between the two devices. It is not chat
over an access point, UDP disguised as ESP-NOW, or ESP-NOW tunneled through the
Terminal connection. TCP/TLS is used to deploy programs and recover logs only.

This is a subset, not a complete Espressif-equivalent stack. The current bridge
accepts exactly32 payload bytes containing the XNOW header. That leaves16 opaque
binary bytes per raw datagram. Applications can define their own binary schema;
the optional message helper is one consumer and is not required by the device
module. The helper's96-byte messages use eight fragments and application ACKs.

Espressif's [official frame/API documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/network/esp_now.html)
describes vendor-specific Action frames, v1 payloads up to250 bytes and v2
payloads up to1470 bytes, as well as peer keys and CCMP encryption. Supporting a
valid subset of those frames does not establish all those capabilities here.
The current plaintext XNOW path is not compatible with every unchanged ESP-NOW
application, encrypted peer or v2 packet.

## Why the Marvell chip can participate

The stock sd8686 Linux driver and radio image identify a Marvell88W8686-family
path. Linux runs on the player's ARM CPU; sd8686.bin runs on the separate radio
CPU. Reverse engineering found an existing radio-side path for receiving and
submitting IEEE802.11 management Action frames. The firmware already handles
the underlying WLAN machinery; the new code adds a bounded format/host bridge.
This is not an Espressif SDK port or a replacement Linux Wi-Fi driver.

There was no usable stock monitor interface to enable. The inspected driver
mode handler admits AUTO/ADHOC/INFRA, and executing the original radio command
dispatcher showed command0x0098 taking its unsupported/default path. An Ethernet
AF_PACKET socket does not expose the radio's original Action frame objects.
Searching for the number0x0098 alone was therefore insufficient.

The original Action handler also offered a useful diagnostic: category127
traffic followed a fallback that produced category255 responses. This was seen
over the air with matching probe fields. It demonstrated reception and an
original response path, but was not ESP-NOW application delivery. The custom
hook must intercept the supported ESP-NOW envelope before that fallback.

## The radio hook

The original subtype dispatch at radio address0xa314 leads Action frames through
the radio's management state machine. The candidate changes the callback veneer
at0xc00026b0 from the original Thumb target0xa315 to the new bridge entry.
Addresses here are radio CPU addresses, not Linux process or kernel addresses.

radio_bridge.c checks the bounded internal wrapper and the accepted envelope:
Action subtype, unprotected frame, category127, OUI18:fe:34, vendor element221,
element length37, type4, version1, and a32-byte payload with valid XNOW header
fields. Its wrapper offsets are internal firmware offsets; they must not be
copied as raw socket capture offsets. The logical vendor content body is47
bytes for this packet shape. Unmatched traffic calls the original handler.

For an accepted data frame, the hook copies the payload and source MAC into its
own mailbox. It never retains an original RX pointer. For TX it reuses original
radio routines: allocator0xd458, header builder0xda00 and submit0xd800 (Thumb
calls use the low-bit-set entry values). The reply is addressed to the peer
whose accepted incoming frame triggered the callback. A successful submit means
queue acceptance, not proof of RF delivery or application reception.

## Reserving memory instead of choosing an apparent gap

An earlier apparent RAM gap was not treated as free memory: physical reads
showed nonzero contents and no owner was established. The accepted candidate
reserves a block from a known original packet pool instead:

| Item | Original | Candidate |
| --- | --- | --- |
| Pool manager |0xc000d5a4| unchanged |
| Pool base/stride |0xc0008b4c /1900 bytes| unchanged |
| Large block count |4|3|
| Reserved interval | none |0xc000a190..0xc000a8fc|

Four coordinated edits reduce the count at0x163ee, redirect the callback and
split two startup-zeroing table entries around the reserved block. The420-byte
Thumb bridge starts at0xc000a190; its92-byte mailbox starts at0xc000a334.
No new SRAM beyond the original pool is assumed. The allocator and startup
zeroing must agree; injecting this code into an unchanged four-block pool would
permit the original allocator to overwrite it.

Offline tests execute original scatter zeroing, pool initialization/allocation/
release, the callback veneer, compiled bridge code and the original boot-reclaim
routine0x11e0. They verify payload survival with RTOS/IRQ effects substituted.
These tests do not prove every ROM alias, concurrency case or high-load capacity
effect. Reducing the pool remains a real tradeoff.

## Linux-to-radio mailbox

The original driver exposes private hostcmd ioctl0x8be4. Radio command0x0086
supports a fixed addressed-word GET/action0 and SET/action1. The native adapter
uses the verified20-byte command layout with response/length checks. Its
internal address lists are bounded; the public SDK does not expose an arbitrary
radio-memory writer.

Before publishing TX, the adapter checks the matching original driver identity,
the three-block candidate layout, exact compiled bridge code and mailbox magic.
It writes the32-byte TX area first and commits the request counter last. The
radio callback observes request != ack, constructs/submits one response, then
publishes its result and acknowledgement. RX uses an odd/even sequence counter:
the host accepts a snapshot only when the counter is unchanged and even.

This mailbox is not a receive FIFO. Another accepted packet can replace the
latest snapshot before Linux reads it. The library reports known misses and
rejects torn reads, but cannot reconstruct overwritten data. Publication,
queue acceptance and application ACK remain distinct. A timeout does not
guarantee that a previously published request was cancelled.

## Why the peer polls

TX currently runs inside the receive callback, not an independent radio task.
Cardputer sends a specific empty XNOW PING every250ms when its transport is idle.
An incoming heartbeat gives the bridge an opportunity to submit pending TX.
The exact empty heartbeat does not replace an unread data/ACK snapshot.

Consequently, the X1060 can originate application messages, but still needs an
incoming peer frame to clock its physical transmission. The mailbox has no
arbitrary destination-MAC argument: TX responds to the current poll source.
This is a significant single-peer/poll-driven restriction, not a complete
independent send scheduler. Another accepted peer must not be assumed isolated
or authenticated by the format checks.

## Loading and returning to normal Wi-Fi

The unchanged Sony loader accepts fw_dir. It can download the candidate from
verified user storage through the unchanged driver, while original radio files
remain under /lib/modules. This changes radio RAM; it does not flash the player,
edit rootfs or modify the Linux module, kernel, initrd or Sony updater.

The owner captures the original1004-byte connection configuration through
libcnmgr, disconnects, unloads, loads the candidate, wakes it, verifies its
identity, initializes RF through original tools and selects the explicit test
channel. Configuration can contain credentials: it stays in RAM and is wiped,
never serialized into logs. The normal AP/IP connection is not used for the
ESP-NOW payloads and concurrent AP/ESP-NOW operation is not qualified.

On stop the owner unloads the candidate, loads original root files, wakes and
verifies the stock radio, performs original initialization, reconnects using
the captured configuration and releases its manager client. Failure retains
ownership for inspection rather than blindly restarting. The nvp zr11/1 command
is a read, not an NVP write. A real failure exposed its stdout/stderr difference;
the parser was corrected and verified on the device before accepted recovery.

The stock-only rehearsal and two candidate tests restored normal Wi-Fi. The
accepted bidirectional test logged RX1, delivered1, unconfirmed0 and done0;
the worker was absent afterward and a new authenticated Terminal connection
verified the original fingerprint, channel8 and four free stock pool blocks.
See the [exact validation identities](../runtime/platform/espnow/VALIDATION.md).

## Remaining work toward a general stack

The active complete-stack requirements and current experimental evidence are
maintained in [full-stack development](ESPNOW_FULL_STACK.md). The old physical
baseline below must not be treated as completion of that objective.

- Accept arbitrary binary ESP-NOW payloads independently of the XNOW format,
  with bounded variable-length parsing. v1/250-byte and optional v2 support
  require separate format/memory work, not just increasing a host constant.
- Add an independent radio TX scheduling path and explicit target selection,
  with buffer ownership, backpressure and error/completion reporting.
- Implement peer management and bounded receive queues. Validate addressing,
  broadcast/unicast behavior, filtering and multiple-peer interference.
- For encrypted interoperability, implement compatible PMK/LMK/CCMP handling,
  nonce/counter and replay behavior; custom payload AES alone is not equivalent.
  Suitability of the original hardware crypto path is not established.
- Qualify channels, repeated sessions, loss/load, sleep/wake, power transitions,
  USB handoff and AP coexistence. The current physical result is channel8 on
  one device pair, not a long-duration or throughput certification.
- Finish the consumer-facing owner/UI lifecycle. The ordinary launcher has a
  roughly2s termination boundary. The detached chat owner and RAM IPC have now
  passed physical client/owner exchange and EOF restoration. The user then
  reported Chat testing passed; exhaustive HOME/sleep/USB behavior remains
  outside that brief report.

Reliability/fragmentation is an optional application service. Remote controls,
telemetry, games and other protocols should not have to adopt chat semantics.
The user SDK therefore separates espnow-core, espnow-device and espnow-message;
see [SDK usage](sdk/ESPNOW.md). No general completion percentage is assigned:
the missing firmware scheduling and crypto/ownership paths need their own proof.
