"""PC-only ECDICT/Unifont conversion to indexed read-only X1000 resources."""
from pathlib import Path
import csv,gzip,hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1];inputs=ROOT/'work/dictionary-inputs';out=ROOT/'work/dictionary-data';out.mkdir(exist_ok=True)
pins={'ecdict.csv':'d1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc','unifont-16.0.04.hex.gz':'f9c8c7802453f47be02677176aeac2342ee96d354fad7a26cedcce48e68e1d9f'}
for n,h in pins.items():assert hashlib.sha256((inputs/n).read_bytes()).hexdigest()==h,n
entries={};skipped=0;duplicates=0
with (inputs/'ecdict.csv').open(encoding='utf-8-sig',newline='')as f:
 for row in csv.DictReader(f):
  word=row['word'].strip();key=word.lower()
  if not key or len(key)>63 or any(ord(c)<32 or ord(c)>126 for c in key):skipped+=1;continue
  sections=[word]
  if row['phonetic']:sections.append('['+row['phonetic']+']')
  for field in ['translation','definition']:
   if row[field]:sections.append(row[field].replace('\\n','\n').replace('\x00',' '))
  if row['exchange']:
   labels={'p':'过去式','d':'过去分词','i':'现在分词','3':'第三人称单数','r':'比较级','t':'最高级','s':'复数','0':'原形','1':'原形变化'}
   forms=[]
   for item in row['exchange'].split('/'):
    k,sep,v=item.partition(':')
    if sep and v:forms.append(labels.get(k,'其他')+' '+v)
   if forms:sections.append('词形变化\n'+'\n'.join(forms))
  if row['tag']:
   labels={'zk':'中考','gk':'高考','cet4':'英语四级','cet6':'英语六级','ky':'考研','ielts':'雅思','toefl':'托福','gre':'GRE'}
   sections.append('词汇范围: '+' / '.join(labels.get(x,x) for x in row['tag'].split()))
  body='\n\n'.join(sections).encode('utf-8')
  if len(body)>65535:skipped+=1;continue
  if key in entries:
   duplicates+=1
   if len(body)<=len(entries[key]):continue
  entries[key]=body
keys=sorted(entries);count=len(keys);base=64+count*16;body=out/'payload.tmp';records=[];offset=base
with body.open('wb')as f:
 for key in keys:
  k=key.encode('ascii');text=entries[key];records.append(struct.pack('<IHHII',offset,len(k),0,offset+len(k),len(text)));f.write(k);f.write(text);offset+=len(k)+len(text)
assert offset<128*1024*1024
header=struct.pack('<8s6I',b'XDICT1\0\0',1,count,16,64,base,offset)+bytes(32)
with (out/'lexicon.dic').open('wb')as f:
 f.write(header)
 for r in records:f.write(r)
 with body.open('rb')as source:
  while True:
   chunk=source.read(1024*1024)
   if not chunk:break
   f.write(chunk)
width=bytearray(65536);bitmap=bytearray(65536*32)
with gzip.open(inputs/'unifont-16.0.04.hex.gz','rt',encoding='ascii')as f:
 for line in f:
  cp,hexdata=line.strip().split(':');cp=int(cp,16)
  if cp>65535:continue
  data=bytes.fromhex(hexdata)
  if len(data)==16:
   width[cp]=8
   for y in range(16):bitmap[cp*32+y*2]=data[y]
  elif len(data)==32:width[cp]=16;bitmap[cp*32:cp*32+32]=data
(out/'font.bin').write_bytes(struct.pack('<8sII',b'XFONT1\0\0',65536,16)+width+bitmap)
report={'entries':count,'skipped_headwords_or_oversized_records':skipped,'merged_case_duplicates':duplicates,'source_pins':pins,'resources':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in [out/'lexicon.dic',out/'font.bin']},'ordering':'ASCII lowercase lexicographic','phonetics':'ECDICT UTF8 plus Unifont BMP glyphs','runtime':'read-only C binary search; PC converter only'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
