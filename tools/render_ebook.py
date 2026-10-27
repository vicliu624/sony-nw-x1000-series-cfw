"""Render the actual C reader UI and write native240x432 PNGs, PC only."""
from pathlib import Path
import subprocess,struct,zlib
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-preview';w.mkdir(exist_ok=True)
cmd=['gcc','-std=c99','-D_DEFAULT_SOURCE','-O1','-Wno-misleading-indentation','-ffunction-sections','-fdata-sections','tools/render_ebook.c','tools/fixtures/ebook_host_stat.c','runtime/apps/ebook/reader.c','runtime/apps/ebook/storage.c','runtime/apps/ebook/ui.c','runtime/apps/dictionary/dictionary.c','runtime/native/sha256.c','runtime/apps/emulators/platform.c','-Wl,--gc-sections','-o',str(w/'render')];cmd[1:1]=['-DMINIZ_NO_STDIO','-DMINIZ_NO_TIME','-DMINIZ_NO_ARCHIVE_APIS','-DMINIZ_NO_DEFLATE_APIS'];cmd[1:1]=[str(p.relative_to(ROOT))for p in sorted((ROOT/'runtime/apps/ebook/epub').glob('*.c'))]+['third_party/epub-miniz/miniz_tinfl.c'];subprocess.run(cmd,cwd=ROOT,check=True);subprocess.run([str(w/'render')],cwd=ROOT,check=True)
for p in w.glob('*.rgb565'):
 rgb=bytearray();raw=p.read_bytes()
 for i in range(0,len(raw),2):
  n=int.from_bytes(raw[i:i+2],'little');rgb.extend((((n>>11)&31)*255//31,((n>>5)&63)*255//63,(n&31)*255//31))
 def chunk(k,b):return struct.pack('>I',len(b))+k+b+struct.pack('>I',zlib.crc32(k+b)&0xffffffff)
 scan=b''.join(b'\0'+rgb[y*720:(y+1)*720]for y in range(432));p.with_suffix('.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
