"""Original fixed pending-table layout and insertion bounds, emulator memory only."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for segment in elf.iter_segments():
 if segment['p_type']!='PT_LOAD':continue
 a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
area=0x71000000;u.mem_map(area,65536);table=area+0x1000;done=area+0xff00
put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
def hook(cpu,pc,size,context):
 if pc==done:cpu.emu_stop();return
 if pc not in (0x116d4,0x33b83c):return
 cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(entry,a,b=0):
 u.reg_write(UC_ARM_REG_R0,a);u.reg_write(UC_ARM_REG_R1,b);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(entry,done+4,count=20000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
first=call(0x489dc,0);second=call(0x489dc,1);assert first==0x66efe8 and second-first==132
u.mem_write(table,bytes([0xa5])*136);call(0x489f0,table)
assert bytes(u.mem_read(table,132))==bytes(132) and get(table+132)==0xa5a5a5a5
call(0x48a14,table,0);assert get(table)==0
for token in range(1,33):call(0x48a14,table,token)
assert get(table)==32 and get(table+128)==32 and get(table+132)==0xa5a5a5a5
call(0x48a14,table,33);assert get(table)==33 and get(table+132)==33
# Reset emulator table; duplicate insertion consumes a second slot too.
call(0x489f0,table);call(0x48a14,table,0x207);call(0x48a14,table,0x207);assert get(table)==2
out=ROOT/'work/player-pending-capacity'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,original_layout_initializer_and_insert_executed=True,table_stride_bytes=132,count_words=1,token_slots=32,zero_token_ignored=True,duplicate_insertion_consumes_slot=True,over_capacity_adjacent_write_observed_in_emulator=True,physical_device_access=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,__import__('pathlib').Path(__file__))},limits=['Over-capacity call intentionally confined to mapped emulator scratch, never a physical target.','No real maximum concurrent stock pending count, unused token namespace or SDK registration position established.','Native callers may enforce capacity/uniqueness outside this insertion helper; no stock-device bug is claimed.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
