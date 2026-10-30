"""Locate producer-side Audio request constants in pinned stock ARM instructions."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));section=elf.get_section_by_name('.text');data=section.data();base=section['sh_addr']
def immediate(instruction):
 n=instruction&255;r=((instruction>>8)&15)*2
 return n if not r else ((n>>r)|(n<<(32-r)))&0xffffffff
rows=[]
for offset in range(0,len(data)-32,4):
 instruction=struct.unpack_from('<I',data,offset)[0]
 if instruction&0x0fe00000!=0x03a00000 or immediate(instruction)!=0x440000:continue
 register=(instruction>>12)&15
 for delta in range(4,28,4):
  next_instruction=struct.unpack_from('<I',data,offset+delta)[0]
  if next_instruction&0x0f000000 in (0x0a000000,0x0b000000):break
  if next_instruction&0x0fe00000 in (0x02800000,0x03800000) and (next_instruction>>16)&15==register and (next_instruction>>12)&15==register:
   low=immediate(next_instruction)
   if 0<low<0x200:rows.append(dict(pc=hex(base+offset+delta),request=hex(0x440000+low),register=register))
   break
  # A different assignment to the tracked register invalidates this short scan.
  if (next_instruction>>12)&15==register and next_instruction&0x0c000000==0 and next_instruction&0x0de00000 not in (0x01000000,0x01200000,0x01400000,0x01600000):break
assert any(r['pc']=='0x18178' and r['request']=='0x440019' for r in rows)
report=dict(stock_sha256=hashlib.sha256(raw).hexdigest(),sites=rows,limits=['This is a short producer-pattern inventory, not a complete ARM dataflow analysis.','A constant alone establishes neither an operation meaning nor a safe callable entry.','No request is sent or enabled by this script.'])
work=ROOT/'work/player-sdk-research';work.mkdir(exist_ok=True);(work/'audio-request-producers.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(rows,indent=2));print('sites:',len(rows))
