"""Replay the analysis Met trampoline and original session wrapper; no device."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from build_player_met_anchor import ROOT,build,patch_met_anchor
candidate,report=build();raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();cases=[]
for result in (0,0x106,0xffffffff):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(candidate)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  address=int(s['p_vaddr']);base=address&~4095;u.mem_map(base,(address-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(address,s.data())
 area=0x71000000;u.mem_map(area,65536);session=area;player=area+0x1000;stack=area+0xf000;cancel=0x12345678
 u.mem_write(session+0x20,struct.pack('<I',player));calls=[]
 regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
 saved=[0xa000+i for i in range(len(regs))]
 for r,v in zip(regs,saved):u.reg_write(r,v)
 def hook(uc,pc,size,context):
  if pc==0x27c614:uc.emu_stop();return
  if pc==0xda84:
   assert uc.reg_read(UC_ARM_REG_R0)==session and uc.reg_read(UC_ARM_REG_R1)==cancel
   assert uc.reg_read(UC_ARM_REG_LR)==int(report['edit']['stub_return'],16)
   calls.append('optional-anchor')
   for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12):uc.reg_write(r,0xdeadbeef)
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0x27b404:
   assert uc.reg_read(UC_ARM_REG_R0)==player and uc.reg_read(UC_ARM_REG_R1)==cancel;calls.append('original-player-maintenance')
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,session);u.reg_write(UC_ARM_REG_R1,cancel);u.reg_write(UC_ARM_REG_SP,stack)
 u.emu_start(0x27c610,0x27c618,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x27c614 and u.reg_read(UC_ARM_REG_R0)==result and u.reg_read(UC_ARM_REG_SP)==stack
 assert [u.reg_read(r) for r in regs]==saved and calls==['optional-anchor','original-player-maintenance']
 cases.append(dict(native_return=hex(result),arguments_restored=True,callee_saved_preserved=True,original_wrapper_executed=True))
original=ELFFile(io.BytesIO(raw));changed=ELFFile(io.BytesIO(candidate));sections=[]
for a,b in zip(original.iter_sections(),changed.iter_sections()):
 assert a.name==b.name and a['sh_addr']==b['sh_addr'] and a['sh_size']==b['sh_size']
 if a.name!='.text':assert a.data()==b.data(),a.name
 sections.append(a.name)
bad=bytearray(raw);struct.pack_into('<I',bad,0x27c610-0x8000,0)
try:patch_met_anchor(bytes(bad))
except ValueError:pass
else:raise AssertionError('Changed original call accepted')
report.update(passed=True,cases=cases,unchanged_nontext_sections=sections,original_player_call_modeled=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/build_player_met_anchor.py','tools/test_player_met_anchor.py']})
w=ROOT/'work/player-met-anchor';(w/'test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
