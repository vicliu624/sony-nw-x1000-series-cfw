# Physical validation scope

On 2026-10-28, a Japanese NW-X1060 on the 1.11 platform and an original
Cardputer on COM17 completed a bidirectional ESP-NOW exchange on channel8.
The X1060 native worker used libxnow0.1.0-dev.8, the original Sony Linux driver
and a modified radio image downloaded into wireless-chip RAM. No system file,
kernel, initrd, NVP value or firmware-update package was installed.

## Results

- X1060 sent a96-byte message in eight fragments. Cardputer received the exact
  text and X1060 recorded its application-level delivery confirmation.
- Cardputer immediately replied with another96-byte message. Its submitted
  sequence/token matched its delivery confirmation. X1060 recorded one complete
  received message. Neither result relies on MAC-send counters alone.
- Native results: RX1, delivered1, unconfirmed0, transport error0, startup
  failure0, restore failure0, done0. The worker was confirmed absent afterward.
- Wi-Fi recovered automatically. A fresh certificate-pinned authenticated
  Terminal command passed the original radio fingerprint, channel8 and original
  four-block pool checks (four free blocks).
- An earlier single-direction test also restored automatically. A separate
  stock-only reload/reconnect rehearsal passed before candidate testing.

An early stock reload attempt stopped at RF initialization because the parser
required nvp's stderr `ok` in its stdout pipe. The original radio was manually
reconnected, the error was reproduced with the real native pipe, and the parser
was corrected before the successful tests. An early reverse-message attempt
was unconfirmed; the successful test triggered the reply from actual reception.
These failures remain distinct from the accepted run.

## Exact tested identities

| Component | Identity |
| --- | --- |
| Native library |0.1.0-dev.8; archive SHA-256 `60f10ce966180df5d9a2c0f92a5ba892f624041c2199c7da812eb2b7dcd9814d` |
| X1060 worker | SHA-256 `72b7313cf95dfd948987c93ba95ccaa337befc480d732a6b6eb5adbd271bfcd7` |
| Radio image | SHA-256 `5bcd7fc8b935612e6e90826826235766130c8226245a385535c8cc2059b39e70` |
| Cardputer | Reported chat0.1.0-dev.2; previously verified installed image SHA-256 `0c1299e0ee43768277e123568e8dc4bc13778ccb725913f74aa2518c161098a0` |

Private raw logs and the machine-checked acceptance report are preserved locally
under work/espnow-over-air-02. The tested worker, library, headers and report are
frozen under work/espnow-known-running-20261028. Fresh SDK builds record their
own archive hash; a changed hash does not inherit this physical acceptance.

## Limits and use

This is experimental, bounded interoperability evidence on one device pair.
It does not qualify long sessions, sleep/wake, USB storage handoff, radio
throughput, hostile peers, multiple peers or every channel. The radio transport
requires Cardputer polling and uses fixed32-byte packets and a latest snapshot;
unconfirmed publication is not cancellation. No encryption is supplied by this
custom application protocol.

The first accepted entry point was an explicit detached native lab worker.
The later chat0.1.0-dev.2 app uses a separate owner and RAM pipes to survive the
launcher's roughly2s termination deadline. Its exact client/owner path passed
physical96-byte exchange, independent-group checks, writer-EOF restoration and
reaping; raw evidence is in work/espnow-chat-owner-live-02. That is not a touch
input/display/HOME acceptance report. The user subsequently reported Chat
testing passed after installation; user-acceptance.json records that distinct
evidence without inventing a per-action test matrix. UI SHA-256 is
34a84f2af68957772ea22e04cc7a053528159da39c72f575b6ed5a3109bca713;
owner SHA-256 is77d0a92af2ec9d96770c4caa34fc6adbdf6f4792b2218e393356b4592318b083.
Original files, user volume and USB ownership remain caller responsibilities.
The charger condition in the lab is operator-confirmed, not hardware-attested.

Build build_exchange_lab.py only after preparing its documented local inputs.
It never deploys or runs the candidate. The worker's --check is read-only;
--detach-exchange-lab --charger-confirmed explicitly changes radio state,
opens a60-second exchange window and then restores stock Wi-Fi. Do not run a
second worker while an earlier worker or its recovery remains unaccounted for.

## dev.11 receive error normalization

Full-runtime regression reproduced raw plaintext format error-1 being treated as
backend IO, stopping the owner without a backend fault. The security adapter now
returns SECURITY_FORMAT for plaintext codec failures. Malformed IE/version cases
are dropped while following valid unknown plaintext and encrypted1470 traffic
continue. A real injected read failure still stops/restores. Host sanitizers and
original-libc ARM fixtures pass; no installed/physical behavior is qualified.

## dev.10 full source interfaces

The complete native full/security/controller implementation now links in the
archive, and SDKalpha.4 exposes optional source services. Public consumers and
whole-archive original-libc ARM link/run checks are offline only. The existing
fixed32 physical report does not qualify variable-length or encrypted RF.
No device app or radio image was installed by these builds. Full-chain source
addresses, candidate identity and qualification gaps are in docs/ESPNOW_FULL_STACK.md.
