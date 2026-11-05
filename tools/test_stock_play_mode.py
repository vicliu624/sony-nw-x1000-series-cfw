"""Replay the exact stock getter; settings are synthetic RAM, no device IO."""
import hashlib,io,json
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for segment in ELFFile(io.BytesIO(raw)).iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000);cases=[]
for value in (0,1,2,3,4,5,255):
 settings=bytes([value])+bytes(31);u.mem_write(0x65e810,settings)
 u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0x1827c,0x50000000,count=10000)
 answer=u.reg_read(UC_ARM_REG_R0);assert answer==(value if value<128 else 0xffffffff)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and bytes(u.mem_read(0x65e810,32))==settings
 cases.append(dict(native_byte=value,result=answer,settings_unchanged=True))
out=ROOT/'work/play-mode-tests';out.mkdir(exist_ok=True)
report=dict(passed=True,actual_stock_getter=True,synthetic_settings=True,device_accessed=False,cases=cases,
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/test_stock_play_mode.py','runtime/platform/player/play_mode.c','runtime/platform/player/stock_play_mode.c')})
(out/'stock-getter-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
