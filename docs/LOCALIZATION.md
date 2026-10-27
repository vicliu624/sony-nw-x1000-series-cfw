# Localization and language application

The project supports Japanese, English, Simplified Chinese and Traditional Chinese
language-pack data. Keep the product strings multilingual even though documentation
is English. External packs and runtime state belong on user storage, with the
system hook kept small and model-specific.

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
