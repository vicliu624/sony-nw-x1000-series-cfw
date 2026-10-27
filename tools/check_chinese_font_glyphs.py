"""Render every new Chinese translation character through original LCF engine."""
from pathlib import Path
import runpy,json,struct,hashlib
ROOT=Path(__file__).resolve().parents[1];n=runpy.run_path(str(ROOT/'work/chinese-wording-review-1/font_glyph_context.py'));u=n['u'];call=n['call'];pixels=n['pixels'];size=n['size'];background=n['background'];width=n['width'];height=n['height'];pointer=n['pointer'];surface=n['surface'];bounds=n['bounds'];rectangle=n['rectangle'];sp=n['sp'];stop=n['stop'];w=ROOT/'work/chinese-font-glyph-check-1'
def glyph(c):
 u.mem_write(pixels,background*(width*height));u.mem_write(pointer,c.encode('utf-16le')+b'\0\0');u.mem_write(sp,struct.pack('<2I',surface,bounds));assert call(0x12bc14,[0,0x13ad1107,rectangle,pointer]);assert not stop,stop
 image=bytes(u.mem_read(pixels,size));locations=[i//4 for i in range(0,size,4)if image[i:i+4]!=background]
 if not locations:return 'empty',0
 x0=min(i%width for i in locations);x1=max(i%width for i in locations);y0=min(i//width for i in locations);y1=max(i//width for i in locations);crop=b''.join(image[(y*width+x0)*4:(y*width+x1+1)*4]for y in range(y0,y1+1));return hashlib.sha256(crop).hexdigest(),len(locations)
results=[]
for label,language in [('zh-CN',6),('zh-TW',7)]:
 assert call(0x1291a0,[0,language]);document=json.loads((ROOT/('translations/x1000-'+label+'.json')).read_text());chars=sorted({c for s in document['translations'].values()for c in s if not c.isspace()and not 0xe000<=ord(c)<=0xf8ff});unknown={glyph(c)[0]for c in ['\uffff','\u0378']};missing=[];seen=[]
 for i,c in enumerate(chars):
  signature,count=glyph(c)
  if signature in unknown or not count:missing.append({'character':c,'codepoint':hex(ord(c)),'pixels':count})
  seen.append({'character':c,'pixels':count})
  if i%100==0:print(label,'glyphs',i,'of',len(chars),flush=True)
 results.append({'language':label,'characters':len(chars),'missing_or_fallback':missing,'rendered':seen,'unknown_signatures':sorted(unknown)})
report={'passed':all(not r['missing_or_fallback']for r in results),'font':'original ucs2-dev-cs-ct.lcf','scope':'Original ARM LCF renderer, one glyph at a time at checked style; compare empty/unassigned fallback. Not every page layout or hardware.','languages':results,'hardware_tested':False};(w/'glyph-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({**report,'languages':[{k:v for k,v in r.items()if k!='rendered'}for r in results]},ensure_ascii=False,indent=2));assert report['passed']
