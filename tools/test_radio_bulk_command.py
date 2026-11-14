"""Original radio command/response instructions with the exact maintained bulk image."""
from pathlib import Path
import sys,struct,json,hashlib,time
from app_registry import ROOT
from radio_test_profile import selected_radio
from build_espnow_full_radio import build
from elftools.elf.elffile import ELFFile
from marvell_firmware import parse
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
OUT=ROOT/'work/radio-bulk-command-tests'/str(time.time_ns());OUT.mkdir(parents=True)
raw=(ROOT/'work/targets-jp/sd8686.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records=parse(raw)
selected=selected_radio()
if selected:
 payload,manifest=selected
else:
 directory=OUT/'radio-build'
 manifest=build(ROOT/'work/targets-jp/sd8686.bin',ROOT/'work/espnow-full-radio-review-3/stock/helper_sd.bin',directory,True,True)
 payload=directory/'radio.elf'
assert manifest.get('bulk_word_commands') and manifest['occupied_span_bytes']<=1900
with payload.open('rb') as f:
 e=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']];symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
request,response=0xc00155b8,0xc0014e4c
def run(action,count,address,size=None,invalid_node=False,patched=True):
 if size is None:size=16+count*4 if action in (0x100,0x101) else 20
 cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
 for base,n in ((0,0x20000),(0xc0000000,0x20000),(0x80000000,0x10000),(0x04000000,0x2000),(0x200000,0x10000)):cpu.mem_map(base,n)
 for r in records:
  if r.command==1:cpu.mem_write(r.address,r.data)
 for a,b in sections:cpu.mem_write(a,b)
 if patched:cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
 cpu.mem_write(0xc000d5a8,struct.pack('<I',0x0003076c))
 for i in range(3):
  p=0xc0008bd8+i*1900;node=p-136
  cpu.mem_write(p-4,struct.pack('<I',node));cpu.mem_write(node+8,struct.pack('<I',p));cpu.mem_write(node+24,struct.pack('<I',0 if invalid_node else 0xc0014728))
  cpu.mem_write(p,bytes((j*7+i+3)&255 for j in range(1760)))
 data=bytes((j*13+11)&255 for j in range(max(4,min(count*4,1536))))
 command=struct.pack('<4H',0x86,size,0x55aa,0)+struct.pack('<HHI',action,count,address)+data
 cpu.mem_write(request,command);cpu.mem_write(response,b'\xa5'*1900)
 cpu.mem_write(0xc0007859,b'\x01');cpu.mem_write(0xc000edf4,b'\0');cpu.mem_write(0xc001452a,b'\x01')
 cpu.reg_write(UC_ARM_REG_SP,0x208000);saved={};copies=[];before=bytes(cpu.mem_read(address,max(4,min(count*4,1536))))
 def hook(u,pc,n,context):
  if pc==0x88d6:
   for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R7,UC_ARM_REG_SP):saved[reg]=u.reg_read(reg)
  if pc==0x9a46:assert saved and all(u.reg_read(reg)==v for reg,v in saved.items())
  if pc==0x9a70:u.emu_stop()
  elif pc==0x9c90:
   dest,source,length=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];copies.append((dest,source,length))
   assert length<=1900
   u.mem_write(dest,bytes(u.mem_read(source,length)));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 cpu.hook_add(UC_HOOK_CODE,hook);cpu.emu_start(0x8079,0x9b40,count=30000)
 assert cpu.reg_read(UC_ARM_REG_PC)==0x9a70
 copied=16 if cpu.reg_read(UC_ARM_REG_R6) else size
 assert copies[-1]==(response,request,copied)
 output=bytes(cpu.mem_read(response,copied));assert struct.unpack_from('<H',output)[0]==0x8086
 status=struct.unpack_from('<H',output,6)[0]
 if not status:
  if action==0x100 and patched:assert output[16:16+count*4]==before
  elif action==0x101 and patched:assert bytes(cpu.mem_read(address,count*4))==data[:count*4]
  elif action==1:assert bytes(cpu.mem_read(address,4))==data[:4]
  else:assert output[16:20]==before[:4]
 else:assert bytes(cpu.mem_read(address,len(before)))==before
 assert bytes(cpu.mem_read(response+copied,4))==b'\xa5'*4
 return {'action':hex(action),'count':count,'address':hex(address),'size':size,'status':status,'full_response_copy':True,'patched':patched}
cases=[]
for action in (0,1,2,0x7777):
 for patched in (False,True):cases.append(run(action,0,0xc0008bf8,patched=patched));assert cases[-1]['status']==0
for action in (0x100,0x101):
 for packet in range(3):
  for count in (1,2,64,371):cases.append(run(action,count,0xc0008bd8+packet*1900+32));assert cases[-1]['status']==0
for kw in ({'count':0},{'count':372},{'count':384},{'count':65535,'size':65532},{'count':4,'address':0xc0008bd9},{'count':4,'address':0x8000a300},{'count':4,'address':0xc0008bd8+1752},{'count':4,'invalid_node':True},{'count':4,'size':20}):
 args=dict(action=0x101,count=4,address=0xc0008bd8);args.update(kw);cases.append(run(**args));assert cases[-1]['status']==2
cases.append(run(0x100,2,0xc0008bd8,patched=False));assert cases[-1]['status']==0
inputs=sorted(set([*manifest['source_hashes'],'tools/test_radio_bulk_command.py','tools/radio_test_profile.py','tools/generate_espnow_full_profile.py']))
report=dict(passed=True,cases=cases,payload_sha256=hashlib.sha256(payload.read_bytes()).hexdigest(),candidate_sha256=manifest['candidate_sha256'],stock_radio_sha256=hashlib.sha256(raw).hexdigest(),original_dispatch_and_response_instructions=True,memcpy_effects_modeled=True,firmware_update_created=False,device_accessed=False,occupied_span_bytes=manifest['occupied_span_bytes'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
(OUT/'instruction-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,cases=len(cases),report=str(OUT/'instruction-report.json'))))
