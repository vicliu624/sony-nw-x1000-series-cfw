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
