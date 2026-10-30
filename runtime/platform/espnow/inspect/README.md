# Radio Inspect0.1.0-alpha.1

Private local diagnostic executable for Japanese X1060 radio research. It is not
an installed app, SDK export, mode switch or ESP-NOW acceptance result. Device
code is C and uses the original Sony loader/libc. Python is PC build/test only.

Build: `.venv/bin/python tools/build_radio_inspector.py` from Linux/WSL at the
repository root. Output: work/radio-inspect/0.1.0-alpha.1/radio-inspect.
The builder requires exact local stock and full-review3 input hashes and emits
only an executable/generated profile/report under work. It never uploads/runs it
on a player. The separate inspect-mock.arm output is a test executable, not a
deployable device tool.

`--help` and `--version` do not access the radio. Explicit `--inspect` checks the
known driver string, matches a416-byte partial code fingerprint for stock JP1.11
or full-radio-experimental-v2, then samples known fields twice. Its only ioctl
request is original hostcmd0086/action0 GET. There is no SET, channel, power,
reload, reset, key-command, file-write or arbitrary-address command-line option.
Driver calls may still block/refuse; no hardware timing guarantee is established.

JSON contains code-profile identity, flag wordc0014528, activationc0014684,
Qc00146e0, registers8000a300/8000200c and the bounded context byteP. Null root/
child gives null context. Non-null pointers must be aligned and fit the known
BSS range. LMK/key-buffer contents and terminal/session credentials are not read.
Fingerprint mismatch, invalid pointer, read failure or differing samples fail
without publishing a partial snapshot. No implicit retry or configuration occurs.

The partial fingerprint is not complete live-image attestation. Equal sequential
samples are not an atomic snapshot and cannot exclude change-and-return, prove
USB/radio ownership or establish hardware ciphertext admission/preservation.
The output explicitly leaves hardware_admission_verified=false. Original/candidate
load/restore and device guard qualification remain separate work.

`.venv/bin/python tools/test_radio_inspector.py` covers14 host observer cases on
actual stock/full code bytes with mocked reads, plus the real ARM CLI through a
GET-only ioctl fixture and original libc. Reports:build.json and tests.json in
the output directory. These checks do not contact a driver/player or validate
physical register reads. No deployment has been performed.
