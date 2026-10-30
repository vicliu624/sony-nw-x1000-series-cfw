# Standard ESP-NOW peer bench0.1.3

Saved console logs can be authenticated without device access:

```sh
.venv/bin/python tools/analyze_espnow_capture_log.py \
  --log work/private-capture/observer.txt --lmk-file work/private-capture/lmk.bin
```

The report distinguishes authenticated captures, invalid records, repeated
ciphertext and conflicting authenticated ciphertext with the same source/PN.
Repeated retry frames are not automatically nonce reuse. A conflict needs review
with key identity and capture provenance; this tool does not prove physical origin
or validate FCS CRC. It emits metadata/hashes, never keys or plaintext. Partial
authentication is reported per record; inspect all rows, not only the exit code.

PC-build candidate for the original ESP32-S3 Cardputer. This is a separate,
headless interoperability bench, not an update to the working chat firmware.
No deployment or physical acceptance is implied. It uses Espressif ESP-IDF5.5.1
through pinned pioarduino55.03.33, without XNOW/chat encapsulation.

Build only: `pio run -d runtime/platform/espnow/standard-peer`.
Do not add an upload target to this command. Outputs stay under project work/.
The native USB Serial/JTAG console is used; the LCD and keyboard are unused.

Starts on channel8 in station mode without connecting to an AP. Wi-Fi NVS is
disabled, storage is RAM, and no peer/key or automatic packet is provisioned.
All commands are newline terminated; MACs are12 hex characters without colons:

- `status`: local version, payload limit, MAC, peer counts, busy and queue drops.
- `pmk <32hex>`: set a RAM-only PMK. No key value is echoed by this application.
- `peer <mac> plain`: add an unencrypted peer, including broadcast.
- `peer <mac> <32hex-LMK>`: add encrypted unicast; explicit PMK required first.
- `delete <mac>`: delete a peer.
- `send <mac> <hex-data>`: send up to1470 binary bytes; `-` requests zero length.
- `capture <mac>`: explicitly enable management capture for one unicast source
  MAC. Only protected, unfragmented Action headers with broadcast address3 and
  successful RX status are copied. Length is bounded to59..1564 including FCS.
- `capture off`: disable promiscuous capture. Capture is off after restart.

CAPTURE lines contain raw frame hex with fcs=1, according to the pinned S3 IDF
sig_len contract. Save only the frame field to a private hex file, then analyze
it with tools/espnow_known_key_frame.py --hex --fcs and an explicit LMK file.
The classifier requires MIC authentication; the callback alone cannot establish
whether a particular hardware path supplied untouched ciphertext. An observer
must receive the other device's transmission; local TX capture is not promised.
Prefer a separate observer without installing the test LMK, to avoid a known-key
hardware receive path changing the observed frame. A successful capture callback
does not itself prove untouched ciphertext or valid MIC.
Capture enabling does not send traffic, install keys or connect an AP. It may
affect radio scheduling; qualify it on the separate bench before using results.
Queued captures can still be printed after capture off; no callback logs/allocates
or performs AES. Captures share the bounded RX queue and its drop counter.
This feature was built/tested offline, not flashed or physically qualified.

RESULT reports the immediate ESP-IDF result. TX reports MAC completion, which
does not prove application delivery. RX reports full binary data and source/dest.
Only one send is outstanding; receive callbacks copy into an eight-entry bounded
queue. Overflow increments drops. TX completion has an independent slot and
keeps sends blocked until consumed by the command task, even when RX is full.
Each loop drains at most eight RX packets and reads up to64 serial bytes, so
continuous RX cannot make the queue-drain loop unbounded. RX data is test data and appears on the console;
do not use personal content or production keys. Command input is not echoed.
Malformed/oversize lines and embedded controls are rejected through newline;
key/command scratch is wiped after use.
Restart clears peers/keys. Use a fresh test LMK after restart: this bench provides
no durable anti-replay or packet-number guarantee across device power cycles.

The bench does not force a wire version; ESP-IDF chooses its transmitted framing.
Validate v1 reception using a separate v1 peer or captured known v1 frames.
Test1/249/250/251/1469/1470 lengths, embedded zeros, broadcast and unicast, wrong
LMK rejection, peer deletion and completion failures. Compare each RX byte with
the submitted input. These tests have not yet been performed on this candidate.
The X1060 still needs qualified radio ownership/load/restore before running the
new full backend; offline tests cannot substitute for that qualification.

`tools/test_standard_espnow_peer.py` compiles the actual bench translation unit
under host ASan/UBSan with mocked IDF/FreeRTOS boundaries. It covers saturated
RX versus completion, binary1470/oversize, malformed hex/control input, busy,
immediate send rejection, encryption setup policy and command scratch erasure.
It does not run Espressif radio firmware or establish over-air interoperability.

The same test also passes15 independently AES-CCM-sealed synthetic frames through
the actual C capture callback, bounded queue and production console serializer,
then verifies exact retained bytes and authenticated payload with the PC classifier.
It covers all three candidate profiles and v1 empty/250 plus v2 empty/251/1470.
Corrupted MICs are rejected after capture. FCS bytes are synthetic placeholders;
this validates serialization and classifier integration, not RF/CRC or hardware
ciphertext preservation. No test LMK is placed in the bench image.

Bench 0.1.3 retains a valid zero-length receive callback even when IDF supplies
a null payload pointer. A null pointer with a positive length remains rejected.
This fixes the bench callback contract; physical empty delivery requires its
own observation and is not established by the host regression.
