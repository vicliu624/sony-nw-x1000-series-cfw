"""Read-only, PC-side audit of the reviewed updater COM dispatch bytes."""
import hashlib,json,struct,uuid
from pathlib import Path
r=Path(__file__).resolve().parents[1]/'work/updater-static-review-1'
e=(r/'extracted/FWUpdater.exe').read_bytes()
d=(r/'extracted/FWUpdaterCom.dll').read_bytes()
for b,h in [(e,'3cf7eb2e354d2e6d3f0cddd06ab67755696579a0d2cc85b68672ecc44ccb3c1c'),(d,'2b7550cd945a8d71d139063fce0ce006bfa6b59ee940f17e5151bdb6e35ebe2f')]:
 if hashlib.sha256(b).hexdigest()!=h: raise SystemExit('Unexpected input')
def require(ok,why):
 if not ok: raise SystemExit(why)
g=e[0x1c3ac:0x1c3bc]
require(g==d[0x2f810:0x2f820],'IID mismatch')
iid_pointer,object_offset,kind=struct.unpack_from('<3I',d,0x2f7c0)
require((iid_pointer,object_offset,kind)==(0x1002f810,8,1),'COM map mismatch')
methods=[]
for table in [0x2f738,0x2f868]:
 method=struct.unpack_from('<I',d,table+12)[0]
 require(method==0x1000b600,'Unexpected transfer method')
 methods.append({'vtable':hex(0x10000000+table),'method':hex(method)})
require(d[0xb6ac:0xb6b1]==bytes.fromhex('e84fdaffff'),'Transfer implementation call mismatch')
require(struct.unpack_from('<I',d,0x2f74c+0x1c)[0]==0x1000b6e0,'Cleanup vtable mismatch')
require(d[0xb76a:0xb76f]==bytes.fromhex('e8b1e1ffff'),'Cleanup implementation call mismatch')
require(d[0x9997:0x999d]==bytes.fromhex('ff15c8e00210'),'DeleteFile import call mismatch')
print(json.dumps({'interface_guid':str(uuid.UUID(bytes_le=g)),'object_offset':object_offset,
 'method_slot':12,'vtables':methods,'implementation':'0x10009100',
 'scope':'Pinned static bytes, no updater or device execution'},indent=2))

