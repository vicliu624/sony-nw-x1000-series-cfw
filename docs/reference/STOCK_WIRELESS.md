# Native wireless reference

Private bindings for Japanese NW-X1050/NW-X1060 on the pinned Sony 1.11 inputs.
Use [platform knowledge](../KNOWLEDGE.md) for input hashes and
[wireless lifecycle](../sdk/WIRELESS.md) for ownership. These are platform facts,
not APIs that third-party apps should copy.

## Native power-off path

| Boundary | Established behavior |
| --- | --- |
| `cnmgr_power_off()` | Client IPC request kind 4 in 1,020 bytes; result at offset 0 of the 1,012-byte response |
| Daemon states 2/3 | Call `cnmgr_wlan_power_off`, then move to internal state 0 when the modeled driver succeeds |
| Daemon states 0/6/7/8 | Reject that request without the power-off driver call |
| Reference counts 1/2 | Same observed power-off behavior; a held cnmgr client is not an exclusive radio lease |
| Wrapper | Close both WLAN pipes, invoke `wlanapi.sh stop`, then `wlanapi.sh unload`; wrapper error 16 propagates shell failures |
| Unload order | `sd8xxx`, `mp200_sdio`, `wlan_pm_register`, `wlan_pwr_ctrl` |
| Power module exit | Call `pwc_regulator_off(0x50806)` followed by original GPIO/PMU reset writes |

Daemon internal states are not the public `cnmgr_get_state()` enumeration.
Disconnect and `cnmgr_fin()` are not replacements for qualified power-off.
Use the original connection-manager path under the correct authority; do not copy
raw register writes into applications.

The original ARM client/daemon/wrapper/exit instructions have offline replay
coverage in `check_cnmgr_power_off.py`, `replay_cnmgr_power_off.py` and
`replay_wlan_power_exit.py`. IPC, driver and register effects are modeled. These
checks establish protocol/software intent, not actual rail voltage, successful
physical unload or standby current.

## Optional exclusive-owner helper

`runtime/platform/espnow/xnow_power_off.c` is an optional internal helper. It
requires the serialized manager owner, held lease, STOPPING/RELEASE boundary and
an independent callback returning exactly 1. Public cnmgr state 4 and uncertain
transitions are refused. Qualified completion requires state 2, all four WLAN
modules absent and matching ownership. Script success alone can hide a partial
unload; residual modules retain uncertainty and the lease.

The finite lab owner selects the remote-specific `radio_stop.c` adapter through
`--power-off-exit`. It restores the controller, powers off and only then releases
the lease/finishes. Borrowed Wi-Fi is refused by this exclusive shutdown adapter.
It is not the shared-session shutdown policy or a default public SDK action.
The original lab assertion/gate is not automatic Sony APF/USB arbitration.

`test_xnow_power_off.py`, `test_xnow_full_control.py` and
`test_full_owner_runtime.py --power-off` exercise admission, reentry, restore,
power-off-before-release and retained failures with modeled hardware effects.
The bounded radio-module parser is shared with native startup/retirement.

## Settings binding boundaries

| JP1.11 location | Meaning |
| --- | --- |
| Table `0x3f611c`, descriptor ID 2 | Original Settings list |
| `0x950f0`, pointer at `0x411350` | Original selection callback |
| `0x74634` | Selected-index conversion; the result is a native transition encoding, not a driver request |
| SWD `sid-050-00` | Row-index wording lookup |
| Analysis RX list `0x4d8000` | Checked 12-entry list including appended transition `0xfd0000` |
| Analysis callback `0x4d8040` | 68-byte guarded selection adapter |
| Analysis anchor LR `0x4d8078` | Opt-in private request interception |
| Label index 11, wording 7310 | Remote Settings row in that analysis profile |

RX list count, Pcs descriptor/pool count, selection and wording are distinct
bindings. Editing a label/list table alone does not establish a visible entry.
Completed-language data places Language at index 10. Publication must follow the
original object/list construction, not a media-list replacement.

The standalone `prepare_remote_settings_row.py` profile is analysis input, not
an installable remote service. Its guard checks the callback, pointer and
48-byte list hashes, original owner and reentry. Default hosts leave the anchor
as ordinary getpid behavior. Opt-in delivery targets a bounded private Settings
queue; registration and activation are separate. Full composition additionally
requires the matching Pcs publication and lifecycle adapters.

Replay covers 190 list/classification cases and 13 callback cases. These are
the declared analysis boundary, not complete native GUI or hardware acceptance.
Keep this profile's addresses/guards private and use current checked builders
instead of copying patch recipes into apps.

## Recorded physical exchange scope

| Profile/test | Established result | Boundary |
| --- | --- | --- |
| Legacy channel-8 Cardputer exchange | Bidirectional 96-byte messages with application ACK; worker exit, original fingerprint/pool and Wi-Fi recovery checked | Exact identities are in the [original validation record](../../runtime/platform/espnow/VALIDATION.md); not every later SDK composition |
| S3/IDF5.5.1 stale-PN test | Durable RX high-water 38 retained; seven REPLAY (-23) rejections, five authenticated 1,470-byte packets, high-water 61 | Stale packet numbers, not exact captured-ciphertext replay |
| S3/IDF5.5.1 wrong-key test | Six AUTH (-22) rejections, then six authenticated 1,470-byte packets after the matching key; first accepted digest matched | Disposable test-key profile, not arbitrary peer/version qualification |

The encrypted test sessions completed and authenticated Terminal access returned.
Raw device records/keys remain private. These results do not establish complete
current-firmware sleep/USB behavior, multi-peer load or FAT power-loss safety.
The current [status table](../STATUS.md) remains the acceptance authority.
