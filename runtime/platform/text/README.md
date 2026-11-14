# Bitmap fonts and read-only lexicons

New native SDK clients select the capability they use:

| Module | Header | Operations |
| --- | --- | --- |
| `bitmap-font` | `x1000/services/bitmap_font.h` | XFONT1 loading, UTF-8 decoding, glyph widths and RGB565 text drawing |
| `lexicon` | `x1000/services/lexicon.h` | Bounded XDICT1 loading, ASCII key search and UTF-8 definition reads |
| `unicode-font` | `x1000/services/unicode_font.h` | Legacy aggregate, retaining the previous font/query declarations and ABI |

The font module does not compile lexicon search or dictionary input/UI. The
lexicon module does not compile glyph drawing. Dictionary multi-tap input and
screen navigation remain in `runtime/apps/dictionary/`. The legacy header retains
input declarations for source compatibility; the SDK does not implement that
app-specific input controller.

`asset_io.h` is private to these two readers. It opens read-only, rejects final
symlinks/nonregular files and validates the stock stat layout and file limit.
These checks are not storage ownership or a sandbox. Callers must qualify their
resource paths and coordinate access with USB/application lifecycle before loading.

Initialize a fresh font or lexicon context, load it once, and close it before
reopening. Do not copy a live owner or close it while another caller uses it.
Open/search functions retain the original success convention: nonzero succeeds.
`dx_font_close` releases the RAM image; `dx_close` closes the lexicon stream.

The XFONT1 image is exactly 2,162,704 bytes: a 16-byte header, 65,536 one-byte widths
and 65,536 glyph records of 32 bytes. Glyphs have 16 rows and widths 0/8/16.
Non-BMP characters use the replacement glyph. `dx_draw` uses the existing
240x432 RGB565 surface and right text edge; it is not an arbitrary-size canvas API.
The caller owns that full buffer and display access.

XDICT1 remains the existing 64-byte header and 16-byte index-record format.
Limits are 128 MiB, two million entries, 63-byte ASCII keys and 65,535-byte text
records. No file format, asset path, save or glyph data is migrated by this split.

Full-checkout checks:

```sh
python tools/test_sdk_text.py
python tools/test_dictionary_app.py
python tools/test_ebook_app.py
python tools/test_ebook_epub.py
```

The SDK client test needs no font/data file. App tests need freshly built apps
and verified font/dictionary assets. They use host/ARM fixtures, not a player;
physical input, USB and sleep/wake acceptance remain separate.
