"""Original read-only sequence getters; does not qualify queue enumeration."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
 if s['p_type']!='PT_LOAD':continue
 a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
area=0x71000000;u.mem_map(area,65536);impl=area;done=area+0xff00
u.mem_write(impl,bytes(0x200));u.mem_write(impl+8,struct.pack('<I',1));u.mem_write(impl+0x24,struct.pack('<I',area+0x1000));before=bytes(u.mem_read(impl,0x200))
def call(pc,index=0):
 u.reg_write(UC_ARM_REG_R0,impl);u.reg_write(UC_ARM_REG_R1,index);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==done and bytes(u.mem_read(impl,0x200))==before
 return u.reg_read(UC_ARM_REG_R0)
def word(va):return struct.unpack_from('<I',raw,va-0x8000)[0]
assert word(0x49a9bc+0x18)==0x2814e4 and call(0x2814e4)==1
assert word(0x49a9bc+0x1c)==0x2814ec and call(0x2814ec,0)==0
assert word(0x49a9bc+0xc)==0x2814d4 and call(0x2814d4)==1
assert word(0x49aa68+4)==0x282048 and call(0x282048)==area+0x1000
w=ROOT/'work/stock-sequence-types';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_getters_execute=True,source_unchanged=True,single_track_count=1,single_track_ordinal=0,multi_group_current_sequence_offset='0x24',source_sha256=hashlib.sha256((ROOT/'tools/test_stock_sequence_types.py').read_bytes()).hexdigest(),stock_sha256=hashlib.sha256(raw).hexdigest(),limits=['Input sequence state modeled; no constructor, ID lifetime, database access, grouped traversal or public queue support qualified.','The group current-sequence getter exposes only its currently selected track sequence; it is not a flattened full group queue.','REA tiny-function selection can resolve to another address; raw vtable entries and executed original instructions are authoritative here.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
