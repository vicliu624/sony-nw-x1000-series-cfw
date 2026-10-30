"""Replay stock volume getter instructions with modeled dependencies; PC only."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));cases=[]
for initialized,enabled,selector,value,expected in [(0,1,0,11,0xfeedface),(1,0,0,11,30),(1,1,0,11,11),(1,1,1,23,23)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  start=int(segment['p_vaddr']);base=start&~4095;size=(start-base+int(segment['p_memsz'])+4095)&~4095
  u.mem_map(base,size);u.mem_write(start,segment.data())
 stack,output,done=0x70000000,0x71000000,0x72000000
 for base in (stack,output,done):u.mem_map(base,65536 if base==stack else 4096)
 def word(address,value):u.mem_write(address,struct.pack('<I',value))
 word(0x612c48,initialized);word(0xe17310,selector);word(0xe17314,value if not selector else 7);word(0xe17318,value if selector else 7);word(output,0xfeedface)
 calls=[]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  if pc==0x326ea0:uc.reg_write(UC_ARM_REG_R0,enabled);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc in (0xdc1c,0xe2c4):
   assert uc.reg_read(UC_ARM_REG_R0)==0xe15f6c;calls.append('lock' if pc==0xdc1c else 'unlock');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done);u.reg_write(UC_ARM_REG_R0,output)
 u.emu_start(0x32a684,done+4,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==done
 result=u.reg_read(UC_ARM_REG_R0);observed=struct.unpack('<I',u.mem_read(output,4))[0]
 assert observed==expected and result==(0 if initialized else 0xfffffffe)
 assert calls==(['lock','unlock'] if initialized and enabled else [])
 cases.append(dict(initialized=initialized,modeled_audio_enabled=enabled,selector=selector,output=observed,result=result,calls=calls))
report=dict(passed=True,stock_sha256=hashlib.sha256(raw).hexdigest(),original_entry='0x32a684',cases=cases,physical_device_accessed=False,limits=['Original instructions execute in Unicorn; initialization/volume memory, output-mode query and mutexes are modeled.','This getter is inside SpiderApp; no external callable endpoint or native SDK backend is established.'])
w=ROOT/'work/player-sdk-research';w.mkdir(exist_ok=True);(w/'stock-volume-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
