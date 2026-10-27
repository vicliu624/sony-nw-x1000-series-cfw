"""Pinned device-font metadata shared by PC build/verification tools."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
FONT_CONFIG=json.loads((ROOT/'sources/qqmusic-font-subset.json').read_text())
FONT_NAME=FONT_CONFIG['filename'];FONT_BYTES=FONT_CONFIG['bytes'];FONT_SHA256=FONT_CONFIG['sha256']
FONT=ROOT/'work/qqmusic-font'/FONT_NAME
assert FONT.stat().st_size==FONT_BYTES and hashlib.sha256(FONT.read_bytes()).hexdigest()==FONT_SHA256
