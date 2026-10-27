"""Prepare the standalone ebook bitmap font, pinned upstream HEX, PC only."""
from pathlib import Path
import urllib.request,gzip,struct,hashlib,json
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-inputs';w.mkdir(exist_ok=True);out=ROOT/'work/ebook-data';out.mkdir(exist_ok=True);p=w/'unifont-16.0.04.hex.gz';source=ROOT/'work/dictionary-inputs/unifont-16.0.04.hex.gz'
if not p.exists():
 if source.exists():p.write_bytes(source.read_bytes())
 else:
  data=urllib.request.urlopen('https://unifoundry.com/pub/unifont/unifont-16.0.04/font-builds/unifont-16.0.04.hex.gz',timeout=60).read();p.write_bytes(data)
assert hashlib.sha256(p.read_bytes()).hexdigest()=='f9c8c7802453f47be02677176aeac2342ee96d354fad7a26cedcce48e68e1d9f'
width=bytearray(65536);bitmap=bytearray(65536*32)
with gzip.open(p,'rt',encoding='ascii')as f:
 for line in f:
  a,b=line.strip().split(':');cp=int(a,16);data=bytes.fromhex(b)
  if cp>65535:continue
  if len(data)==16:
   width[cp]=8
   for y in range(16):bitmap[cp*32+y*2]=data[y]
  elif len(data)==32:width[cp]=16;bitmap[cp*32:cp*32+32]=data
font=out/'font.bin';font.write_bytes(struct.pack('<8sII',b'XFONT1\0\0',65536,16)+width+bitmap);assert hashlib.sha256(font.read_bytes()).hexdigest()=='05d7a20a4b3d3c8916d18b47bc5deba470fd9d29ea28d46fcab5acc9605c2924';print('Pinned standalone ebook font prepared')
