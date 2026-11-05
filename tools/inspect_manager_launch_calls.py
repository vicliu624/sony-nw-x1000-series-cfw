"""Pinned direct ARM manager launch-call inventory; PC-only analysis."""
import io,struct,json,hashlib
from pathlib import Path
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
root=Path(__file__).resolve().parents[1]
r=(root/'work/stock-manager-runtime-probe/root/usr/local/bin/sysmgrd').read_bytes()
assert hashlib.sha256(r).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
d=Cs(CS_ARCH_ARM,CS_MODE_ARM); rows=[]; references=[]
for s in ELFFile(io.BytesIO(r)).iter_segments():
 if s['p_type']!='PT_LOAD' or not s['p_flags']&1:continue
 data=s.data();base=int(s['p_vaddr'])
 for i in range(0,len(data)-3,4):
  w=struct.unpack_from('<I',data,i)[0]
  if w&0x0e000000!=0x0a000000 or w>>28==15:continue
  a=base+i;t=a+8+(((w&0xffffff)^0x800000)-0x800000)*4
  if t not in (0x110e0,0x112c4,0xa4c4,0xbd24,0xcb50):continue
  ctx=[f'{x.address:x} {x.mnemonic} {x.op_str}' for x in d.disasm(data[max(0,i-64):i+20],base+max(0,i-64))]
  rows.append(dict(address=hex(a),target=hex(t),context=ctx))
for seg in ELFFile(io.BytesIO(r)).iter_segments():
 if seg['p_type']!='PT_LOAD':continue
 data=seg.data();base=int(seg['p_vaddr'])
 for i in range(0,len(data)-3,4):
  value=struct.unpack_from('<I',data,i)[0]
  if value in (0xa4c4,0xbd24,0xcb50):references.append(dict(address=hex(base+i),target=hex(value),executable=bool(seg['p_flags']&1)))
out=root/'work/manager-launch-calls';out.mkdir(exist_ok=True)
report=dict(stock_sha256=hashlib.sha256(r).hexdigest(),device_accessed=False,direct_calls=rows,literal_wrapper_references=references,limits=['Direct ARM branch inventory only; indirect callers and reachability are not proven.','Internal launch functions are not evidence of an external IPC operation or authorization.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
