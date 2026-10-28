# README image provenance

This directory contains selected documentation images, not private device photos
or a copy of the ignored work tree. manifest.json records hashes and source-frame
paths for each image. No real account, live QR, terminal connection code, private
key, ROM, album artwork or downloaded music is included.

| Image | Provenance |
| --- | --- |
| launcher-market.png | Actual ARM launcher framebuffer and shared C market painter; example package metadata |
| market-details.png | Actual ARM detail painter; synthetic version states |
| qqmusic.png | Actual ARM QQ Music UI fixture; synthetic collections, song and import data |
| pocket-fm.png | Native FM rendering fixture; no RF/audio qualification |
| app-icons.png | Original project vector-derived icon set |

The images do not establish hardware installation, network account authorization,
RF reception, audio output, USB handling or sleep stability. GUI states such as
an imported result are synthetic fixture states unless separately documented as
physical evidence. Chinese UI text is product content; documentation is English.

Regeneration uses optional PC Pillow13.0.0 and existing pinned build inputs:

```sh
.venv/bin/python tools/build_launcher_art.py
.venv/bin/python tools/market_metadata.py
.venv/bin/python tools/build_app_list_review.py
.venv/bin/python tools/render_launcher_preview.py --showcase
.venv/bin/python tools/render_market_details.py
.venv/bin/python tools/test_qqmusic_ui.py
.venv/bin/python tools/build_fm_radio.py
.venv/bin/python tools/prepare_readme_gallery.py
.venv/bin/python tools/check_readme_gallery.py
```

Only the final small PNG contact sheets and their manifest belong here. Source
frames and test output stay under ignored work/. Normal firmware/app builds do
not regenerate documentation or depend on those local frames. The shared Noto
raster/QQ font notices are retained under third_party/qqmusic-stb/Noto-OFL.txt;
application artwork is original project work.
