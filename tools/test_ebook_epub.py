from pathlib import Path
import subprocess,sys,json
ROOT=Path(__file__).resolve().parents[1]
w=ROOT/'work/epub-tests';w.mkdir(exist_ok=True)
book=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/epub-tests/input.epub'
assert book.is_file(), 'Pass a local EPUB path as the first argument'
src=['tools/test_ebook_epub.c','tools/fixtures/ebook_host_stat.c','runtime/apps/ebook/reader.c','runtime/apps/ebook/storage.c','runtime/apps/ebook/ui.c','runtime/apps/dictionary/dictionary.c','runtime/native/sha256.c','runtime/apps/emulators/platform.c']+[str(p.relative_to(ROOT))for p in (ROOT/'runtime/apps/ebook/epub').glob('*.c')]+['third_party/epub-miniz/miniz_tinfl.c']
flags=['-std=c99','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-stack-protector','-fno-builtin','-O1','-g','-D_DEFAULT_SOURCE','-DMINIZ_NO_STDIO','-DMINIZ_NO_TIME','-DMINIZ_NO_ARCHIVE_APIS','-DMINIZ_NO_DEFLATE_APIS','-ffunction-sections','-fdata-sections','-Wl,--gc-sections']
subprocess.run(['gcc',*flags,*src,'-o',str(w/'full-book')],cwd=ROOT,check=True)
r=subprocess.run([str(w/'full-book'),str(book)],cwd=ROOT,capture_output=True,text=True,timeout=120)
print(r.stdout,r.stderr);assert r.returncode==0
(w/'full-book.json').write_text(json.dumps({'passed':True,'stdout':r.stdout,'hardware_tested':False},indent=2))

lib=ROOT/'work/arm-signal-tests/lib'
arm_src=[x for x in src if x!='tools/fixtures/ebook_host_stat.c']+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-D_FILE_OFFSET_BITS=64','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*arm_src,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(w/'full-book-arm')],cwd=ROOT,check=True)
r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(w/'full-book-arm'),str(book)],cwd=ROOT,capture_output=True,text=True,timeout=180)
print('ARM',r.stdout,r.stderr);assert r.returncode==0
(w/'full-book-arm.json').write_text(json.dumps({'passed':True,'stdout':r.stdout,'hardware_tested':False},indent=2))
subprocess.run(['gcc',*flags,'-fsanitize=address,undefined','-fno-omit-frame-pointer',*src,'-o',str(w/'full-book-asan')],cwd=ROOT,check=True)
r=subprocess.run([str(w/'full-book-asan'),str(book)],cwd=ROOT,capture_output=True,text=True,timeout=120)
print('ASAN',r.stdout,r.stderr);assert r.returncode==0
(w/'full-book-asan.json').write_text(json.dumps({'passed':True,'stdout':r.stdout,'hardware_tested':False},indent=2))

# Original, redistributable fixtures: EPUB 3 nav, CSS, inline emphasis; corrupt and encrypted books rejected.
import zipfile,io
container='<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>'
opf='<package version="3.0"><metadata><title>Fixture</title></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest><spine><itemref idref="a"/></spine></package>'
chapter='<html><head><style>p{text-indent:2em}h1{text-align:center}</style></head><body><h1 id="start">Fixture</h1><p>Original test text <b>bold</b> <i>italic</i> <sup>2</sup> <sub>3</sub> &amp; 中文。</p></body></html>'
nav='<html><body><nav epub:type="toc"><ol><li><a href="a.xhtml#start">Start</a></li></ol></nav></body></html>'
for kind in ['valid','encrypted','traversal','crc']:
 path=w/(kind+'.epub')
 with zipfile.ZipFile(path,'w',zipfile.ZIP_STORED)as z:
  for name,data in [('mimetype','application/epub+zip'),('META-INF/container.xml',container),('OPS/book.opf',opf),('OPS/a.xhtml',chapter),('OPS/nav.xhtml',nav)]:z.writestr(name,data)
  if kind=='encrypted':z.writestr('META-INF/encryption.xml','<encryption/>')
  if kind=='traversal':z.writestr('../escape','invalid')
 if kind=='crc':
  data=path.read_bytes().replace(b'Original test text',b'Corrupt! test text');path.write_bytes(data)
 args=[] if kind=='valid'else['reject']
 r=subprocess.run([str(w/'full-book-asan'),str(path),*args],cwd=ROOT,capture_output=True,text=True,timeout=30)
 # Both the generated EPUB3 fixture and rejection fixtures use the production parser.
 assert r.returncode==0,(kind,r.stdout,r.stderr)
(w/'malformed.json').write_text(json.dumps({'passed':True,'cases':['encrypted','traversal','crc'],'hardware_tested':False},indent=2))
