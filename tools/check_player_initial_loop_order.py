"""Pinned original-instruction evidence for event dispatch before SDK anchor."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
source=ROOT/'work/targets-jp/SpiderApp';raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw))
def word(address):
 segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address<s['p_vaddr']+s['p_filesz'])
 return struct.unpack_from('<I',segment.data(),address-segment['p_vaddr'])[0]
def branch(address,target,link=True):
 instruction=word(address);assert instruction>>24==(0xeb if link else 0xea)
 offset=instruction&0xffffff
 if offset&0x800000:offset-=0x1000000
 assert address+8+offset*4==target
branch(0xff28,0x106c8);branch(0xff3c,0xa6968)
branch(0xff44,0xff1c,False)
assert word(0x10728)==0x979ff103
assert word(0x10730+(0x42-2)*4)==0x10970
branch(0x10974,0x10660);branch(0x10684,0x71530,False)
branch(0x7155c,0x17c608)
assert word(0x71cd4)==0xe3a01007
branch(0x71cd8,0x112fc)
report=dict(passed=True,stock_binary_sha256=hashlib.sha256(raw).hexdigest(),
 event_dispatch_call='0xff28 -> 0x106c8',later_sdk_anchor='0xff3c (original no-op callee)',
 root_event_class_route=['0x42','0x10970','0x10660','0x71530','0x17c608'],
 activation_action='0x71cb8 sets command7 at0x71cd4, calls coordinator at0x71cd8',
 finding='A queued Root activation may be dispatched in the first loop before the SDK binding anchor; unbound command7 is not merely an artificial call order.',
 limits=['Static branch/order checks, not execution of the complete startup path.',
 'Root readiness, queue contents and real thread timing are not established here.',
 'The separate Root-state replay establishes which supplied states select the activation action.'],
 device_accessed=False,physical_boot_verified=False,
 source_hashes={'tools/check_player_initial_loop_order.py':hashlib.sha256((ROOT/'tools/check_player_initial_loop_order.py').read_bytes()).hexdigest()})
(ROOT/'work/player-initial-loop-order.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
