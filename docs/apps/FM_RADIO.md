# Pocket FM

Source: runtime/apps/fm-radio. Build: tools/build_fm_radio.py. This is an independent
native application using the stock tuner/audio drivers, not a replacement Sony
FM binary. Its skeuomorphic micro-radio interface was accepted by the user.

Implemented: 76.0-108.0MHz,100kHz steps, numeric entry, band wrapping, bounded
cancelable search,64 favorites and64 search results, and user-storage persistence.
Scan results are committed transactionally; cancellation restores the prior tune.
Corrupt state falls back to the previous valid slot; narrow-band records migrate.

The Si470x adapter identifies the stock V4L1 interface, writes only SYSCONFIG2
register5 to select Japan-wide76-108, preserves unrelated bits and50/100kHz spacing,
and converts200kHz to100kHz only when needed. It reads configuration back and
restores the original word on cleanup. The UI range alone is not RF expansion.

Tuning requires cached GETFREQ **and** hardware completion/channel confirmation.
Stock signal judgment is binary, not continuous RSSI. Fixed ARM32 ioctl structures
are used; private GETREGALL is excluded because its declared/actual copy sizes
disagree. Never substitute a host V4L structure.

Audio preparation snapshots stock mixer fields before tuner open, mutes output,
selects tuner/ADC and preserves analog headphone volume. Cleanup quiesces the tuner,
restores band and mixer fields, and reports retry/restoration errors. The public
mute API cannot restore arbitrary internal bit0x100; incompatible starting state
is rejected. No guessed codec-reset or power proc operation is used.

Data belongs at verified `/contents/HOMEBREW/data/fm-radio/`, with CRC-protected
double slots. Demo mode uses a synthetic tuner and does not persist state. Safe
help/version/selftest entries do not establish reception.

Live research confirms an I2C Si470x binding and R2A15602LG audio driver. Exact
silicon subtype, actual90-108MHz stations, sound and restoration remain unverified.
The user paused the proposed FM hardware test in favor of Wi-Fi analysis; no tuner
or sound state was changed in that investigation. No AM/RDS/recording feature is
implied. Preserve the original Sony FM program, system files and NVP.
