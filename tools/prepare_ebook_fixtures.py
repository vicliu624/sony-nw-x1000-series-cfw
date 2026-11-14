"""PC-only original text/encoding fixtures. No copyrighted books or device I/O."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-tests/books';w.mkdir(parents=True,exist_ok=True)
text='ASCII 中文测试 café 𠀀 🙂\r\n下一行\r终行\n'
for enc,name in [('utf-8-sig','codec-utf8.txt'),('gb18030','codec-gb.txt'),('utf-16','codec-le.txt'),('utf-16-be','codec-be.txt')]:
 data=text.encode(enc)
 if enc=='utf-16-be':data=b'\xfe\xff'+data
 (w/name).write_bytes(data)
book=(ROOT/'examples/books/阅读示例.txt').read_text(encoding='utf-8');(w/'阅读示例.txt').write_text(book,encoding='utf-8');(w/'长篇测试.txt').write_text(book*8,encoding='utf-8');(w/'空白.txt').write_bytes(b'');(w/'invalid.txt').write_bytes(b'\xe4\xb8\xffA\r\n');(w/'long-line.txt').write_text('很长的一段文字 without any newlines '*3000,encoding='utf-8')
with(w/'too-large.txt').open('wb')as f:f.truncate(64*1024*1024+1)

# Clean-checkout EPUB tests use original text, not a locally supplied book.
import struct,zlib,zipfile
epub=ROOT/'work/epub-tests';epub.mkdir(exist_ok=True)
def chunk(kind,data):
 return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\x20\x60\xa0'))+chunk(b'IEND',b'')
with zipfile.ZipFile(epub/'original-fixture.epub','w',zipfile.ZIP_DEFLATED) as archive:
 archive.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED)
 archive.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
 manifest=''.join(f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>' for i in range(8))
 spine=''.join(f'<itemref idref="c{i}"/>' for i in range(8))
 archive.writestr('OPS/book.opf','<package version="3.0"><metadata><title>Original text fixture</title></metadata><manifest>'+manifest+'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="pixel" href="pixel.png" media-type="image/png"/></manifest><spine>'+spine+'</spine></package>')
 nav=''.join(f'<li><a href="c{i}.xhtml#start">Chapter {i}</a></li>' for i in range(8))
 archive.writestr('OPS/nav.xhtml','<html><body><nav epub:type="toc"><ol>'+nav+'</ol></nav></body></html>')
 archive.writestr('OPS/pixel.png',png)
 for i in range(8):
  archive.writestr(f'OPS/c{i}.xhtml',f'<html><body><h1 id="start">Chapter {i}</h1><p>Original 中文 fixture: <b>bold</b>, <i>italic</i>, x<sup>2</sup> and H<sub>2</sub>O.</p><p><a href="c{(i+1)%8}.xhtml#start">Next chapter</a></p><img src="pixel.png"/></body></html>')
