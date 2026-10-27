"""Generate GB18030 mapping resources using pinned CPython codec, PC only."""
from pathlib import Path
import sys,struct,hashlib,json
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'work/ebook-data';out.mkdir(exist_ok=True)
table=[]
for a in range(0x81,0xff):
 for b in list(range(0x40,0x7f))+list(range(0x80,0xff)):
  try:s=bytes([a,b]).decode('gb18030');cp=ord(s)if len(s)==1 else 0xfffd
  except UnicodeError:cp=0xfffd
  table.append(cp)
ranges=[];start=last=code=previous=None
for i in range(126*10*126*10):
 n=i;b4=n%10+0x30;n//=10;b3=n%126+0x81;n//=126;b2=n%10+0x30;b1=n//10+0x81
 try:s=bytes([b1,b2,b3,b4]).decode('gb18030');cp=ord(s)if len(s)==1 else None
 except UnicodeError:cp=None
 if cp is not None and start is not None and i==last+1 and cp==previous+1:last=i;previous=cp;continue
 if start is not None:ranges.append((start,last,code))
 if cp is None:start=last=code=previous=None
 else:start=last=i;code=previous=cp
if start is not None:ranges.append((start,last,code))
raw=struct.pack('<8sII',b'XGB1803\0',len(table),len(ranges))+struct.pack('<'+str(len(table))+'I',*table)+b''.join(struct.pack('<III',*x)for x in ranges)
p=out/'gb18030.bin';p.write_bytes(raw);report={'source':'CPython standard library gb18030 codec','python':sys.version,'two_byte_entries':len(table),'four_byte_ranges':len(ranges),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'not_a_GB18030_2022_conformance_claim':True};(out/'encoding.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
