# Bounded image conversion

The SDK `images` module owns in-memory PNG/JPEG validation, RGB565 thumbnails,
lossless PNG QR decoding, baseline JPEG conversion and FLAC PICTURE extraction.
It performs no filesystem, network, account or display operations. QQ Music owns
artwork acquisition, track/album identity, caching and presentation policy.

Import `x1000/services/images.h` and select the `images` SDK module. Historical
`qq_image_*`/`qq_picture_*` names remain source-compatible. Implementation and
the pinned stb dependencies are selected by `sdk/services.json`; callers do not
need another application's source or builder.

Calls must be serialized. The module uses process-local decode accounting and
a reentrancy flag, not a thread mutex. Decoder allocations have a 16 MiB ceiling;
PICTURE parsing additionally uses its bounded temporary block. Buffers belong to
the caller and input/output must not overlap. No decoded heap is retained after
an operation. Read the header for each operation's independent input, output and
dimension limits.

Validated baseline JPEG bytes are preserved. PNG/progressive inputs become
baseline JPEG with alpha composited on white. QR decoding keeps whole pixels;
the caller supplies the quiet zone. PICTURE accepts a front-cover image, ignores
nonfront entries and never fetches URL pictures.

Offline checks in the full research checkout:

```sh
python tools/verify_qqmusic_artwork.py
python tools/test_qqmusic_metadata.py
```

These exercise pinned codecs and the metadata consumer on host/ARM with synthetic
images. They do not establish physical Sony/Core2 display, transfer or timing.
