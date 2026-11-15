# qqmusic

Native application sources. See [application guide](../../../docs/apps/QQ_MUSIC.md).

## Independent build

From the repository root, run `python tools/build_app.py qqmusic`.
This folder owns app.json, VERSION, assets and build.py. See the
[application specification](../../../docs/APP_SPEC.md) for package fields, shared
adapters, configurable build outputs and app-specific input requirements.

The app decodes login QR images and cover previews for its own screens. When it
imports a track, it prefers the source's embedded front cover, including one
carried in a FLAC PICTURE block. The image helpers prepare a baseline JPEG for
the import writer, which embeds it in the MP3's standard ID3v2.3 APIC frame.
After the MP3 enters the Sony library, the player can retrieve its cover through
the same media database interface it uses for other tracks.

The helpers take caller-owned nonoverlapping buffers and use a process-local
decode budget. The app serializes calls.
