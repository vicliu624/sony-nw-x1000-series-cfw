# Localization

Physical follow-up on 2026-11-04 reports only ten Settings entries and no
language selector. The final local candidate's native list-query replay returns
twelve Japanese entries, but actual page construction/visibility and installed
payload identity are not yet reconciled. Treat the selector as unverified on
hardware; do not use the query result alone to claim it is visible.

The previous media-list adapter did not affect the physical menu and is no
longer included. The current combined host makes a data-only edit to the native
Pcs Settings descriptor (control0x61/resource5000): fields21/32 change from10 to
the enabled language/remote selection count, while capacity49 and all other
templates remain intact. No extra ARM adapter or media-list call redirection is
needed. tools/test_native_settings_count.py executes original Home request,
Pcs registration, native pool allocation and real widget object construction;
it reproduces ten items from the failed player and twelve from the corrected
player. Standard memory-copy/clear and queue transport are modeled. This is not
complete page rendering, live scrolling/selection or physical acceptance.
The standalone localization-only builder's older evidence must not inherit the
combined-host validation claim. Failed adapter sources and old reports remain
separate private evidence; source replacements invalidate their freshness.

The project supports Japanese, English, Simplified Chinese and Traditional Chinese
language-pack data. Keep product strings multilingual even though documentation
is English. The current profile uses completed built-in STX files and the original
Settings language selector. It removes external-pack hooks and user-volume
language preference reads. A separate Language app is not part of this profile
or its release/setup packages. Historical external/cache candidates remain
separate; retaining their sources does not qualify them for current firmware.

`tools/prepare_builtin_localization.py` prepares a root-resource overlay from
the retained translations. Against candidate9, Japanese is unchanged and complete
English/Simplified/Traditional replacements add48228 bytes in total, before block
rounding. Required Japanese wording entries are all present. It produces no UPG
and does not yet remove hooks or expose the Settings selector. Final occupancy
must be recomputed against the selected firmware base, not inferred from ZIP size.

Pinned stock analysis identifies UI:LANGUAGE, category11/item0xb00. The getter
is0x3d6dc and the original setter/apply wrapper is0x3dedc. Confirmation callback
0x89a38 maps English0xf80101 to setting1, Japanese0xf80107 to7, Simplified
0xf8010a to9 and Traditional0xf80109 to10. Do not derive the Chinese settings
from menu-item suffix order. `tools/test_builtin_language_selector.py` executes
the original confirmation instructions for both market layouts and cancel cases
(16 passes); persistence and UI boundaries are modeled, not device-qualified.
Function0x39af8 belongs to reset-settings flow and is not the language setter.

`tools/prepare_builtin_language_settings.py` enables the existing language item
without changing the market classification. It retains the Japanese Settings
list's ten entries, appends0xf80000 in an unused44-byte read-only region and
updates only that list pointer/count. Original selector/callbacks remain intact.
ARM replay covers95 list IDs under both classifications (190 cases), requiring
all other lists unchanged. ELF length is unchanged. This preserves the original
language picker rather than claiming a new four-item UI: four language resources
are completed; other native languages retain their original coverage. Hardware
visibility, persistence and sleep/wake remain unqualified. Remote host composition
must use this new base, not silently reintroduce the external cache base.

`tools/test_builtin_player_composition.py` composes the owner, Met and prepare
anchors with this exact pinned Settings base. It verifies native SDK guard spans
before the declared Met edit, preserves the restored STX callsites and Settings
data, and reconstructs the complete input by reverting only declared SDK edits.
Changed code, occupied bridge data, changed language data and a mismatched profile
are rejected. `tools/build_player_host.py --managed-host --engine-provider
--native-prepare --builtin-localization` builds the paired ARM host in a separate
output directory; the legacy external-language build remains separate. Both are
analysis artifacts, not firmware packages or sleep/wake acceptance. Final release
assembly still needs the integrated SDK startup policy and a player-file bundle
that omits the old Language app and activation files.

`tools/release_firmware.py --builtin-localization` now builds the localization
profile directly from Homebrew sources and the checked-in translations. It does
not add process-cache hooks or generate external language files. Its Settings
edit is the same pinned edit checked by the ARM list replay. This option alone
does not activate the player SDK or add Wireless Remote to Settings.
`tools/test_builtin_firmware.py` independently unpacks that local UPG, compares
the retained completed translations, verifies the unchanged first three
components and checks archive changes and existing metadata. The tested build
adds98754 regular-file bytes versus stock; a4KiB regular-file allocation estimate
adds106496 bytes. These figures exclude filesystem metadata/reserved blocks and
are not a free-space or hardware qualification. No extra original-player copy is
included in this profile.

Source is in runtime/apps/language; shared Sony lifecycle/resource code remains
under runtime/native. Builders include build_language_packs.py,
build_external_language_app.py, build_external_language_bridge.py and
build_process_language_cache.py. They are PC tools, not device scripts.

Wording and resource analysis distinguishes STX strings, SWD layouts and indexed
TEXGRP graphics. style.dat has204 layout slots and32 control slots per layout;
the external table was compared with SpiderApp's embedded copy. That does not
make arbitrary layout edits safe: dynamic controls, transforms and Home mapping
remain separate concerns.

Candidate11 had an intermittent unresponsive state after sleep. Candidate12 uses
a process-owned language RAM cache, avoiding file reopening during GUI rebuild.
Offline cache/resource checks passed, but physical sleep/wake stability remains
unverified. Do not describe this as a proven fix or trigger repeated device tests
as a side effect of source maintenance.

Preserve known-running rollback packages and incident evidence under ignored
local directories. Historical candidate names, input hashes and failure reports
must not be rewritten to fit the current version or source layout.
