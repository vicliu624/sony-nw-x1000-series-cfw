# Third-party tools

The new X1000 SDK facade, templates and SDK-specific tools retain the MIT notice
in sdk/LICENSE; reused project adapters retain their source notices. Host-only
interactive previews dynamically link SDL2 (zlib license, https://www.libsdl.org/),
provided by the development system and never shipped in a device app. SDK apps
using the existing Noto raster include its SIL OFL notice. Source SDK archives
contain no Sony libc/loader or other proprietary binary.

The shared launcher/market proportional ASCII bitmap is rasterized from the pinned
Noto Sans CJK SC Regular input recorded in sources/qqmusic-font-source.json.
It is licensed under SIL OFL1.1; the retained notice is
third_party/qqmusic-stb/Noto-OFL.txt and accompanies launcher/store delivery.
Application icons under runtime/apps/<id>/assets are original project artwork generated
by tools/build_launcher_art.py. Optional PC design/rendering uses Pillow13.0.0;
no Pillow or font/image decoder is linked into the device list renderer.

JPEG/PNG memory processing uses official stb headers at 003501f6d7a8668ce8b6d875e34dd97ad0d5d5b5 (https://github.com/nothings/stb), MIT alternative selected. Headers and full dual-license notice retained in third_party/qqmusic-stb/, SHA256 manifest sources/qqmusic-image-sources.json. No source changes; single-threaded/no-SIMD/no-file profiles and allocation limits are configured in our C adapter.

Codec candidates are vendored in third_party/qqmusic-codecs/: Xiph Tremor 820fb3237ea81af44c9cc468c8b4e20128e3e5ad and libogg 06a5e0262cdc28aa4ae6797627a783b5010440f0 (retained BSD-style COPYING), and Shine ab5e3526b64af1a2eaa43aa6f441a7312e013519 (retained GNU Library GPL version 2 COPYING). Official origins and per-file upstream/local SHA256 are in sources/qqmusic-codec-sources.json. Local Shine changes select generic C, calculate frame slots exactly, and drain final cached bytes. These are private development candidates; distribution/relink/license obligations require review before any release. Original Sony libc/libm are build inputs under ignored work/ and are not redistributed.

QMC2 C data/key processing adapts the MIT-licensed qmunlock reference already used by Walkman Mate (upstream https://github.com/mary20050520/qmunlock , recorded commit 8c197956a13105728119c3dc03fcb47cdbfdbb54). The local reference includes documented compatibility fixes; its exact SHA256 is d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b. Reference and full MIT notice retained in third_party/qmc-reference/. Python reference runs on the development PC only; device implementation is C. No actual account key or encrypted music is bundled.

QQ Music protocol work cross-checks the locally installed qqmusic-api-python 0.8.2 (GPL-3.0-or-later), https://github.com/l-1124/QQMusicApi . Endpoint/parameter flow references and source hashes are recorded in docs/apps/QQ_MUSIC.md. No Python package is bundled or executed on the device. Treat the protocol adaptation as GPL-3.0-or-later for distribution review; upstream license is retained under third_party/qqmusic-protocol-reference/LICENSE. No application release or distribution is performed.

`third_party/rockbox-upgtools` is Rockbox's Sony UPG utility, GPL-2.0-or-later as stated in its retained source headers. File hashes and upstream location are in sources/rockbox-tools.json. It provides the DES-equivalent key search, independent extraction and exact original-package reconstruction used in this research. Using these tools does not install Rockbox on the device.

Sony executables, extracted system files and official source archives remain local under ignored firmware/ and work/. Download URLs and hashes are recorded; no license to redistribute proprietary Sony code is implied.

A820 homebrew is a research reference, not yet incorporated or ported. Its license and hardware assumptions must be reviewed before reuse.

Optional research uses vmlinux-to-elf 1.3.6 (GPL-3.0-or-later, https://github.com/marin-m/vmlinux-to-elf) to recover analysis-only kernel symbols, pyelftools and Unicorn 2.1.4 to inspect and replay bounded instruction slices. These are host research tools, not linked into a device application. The recovered Sony kernel ELF remains ignored and is not a firmware output.
