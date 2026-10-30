"""Run the native volume binding against original AudioC instructions, PC only."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-volume-host';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/stock_image.c','runtime/platform/player/stock_volume.c','runtime/native/sha256.c','tools/fixtures/stock_host_image.c'];artifact=work/'profile.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
program=artifact.read_bytes();helper=ELFFile(io.BytesIO(program));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
stack,context,output,done=0x70000000,0x71000000,0x71000100,0x72000000
results=[]
def signed(v):return v if v<0x80000000 else v-0x100000000
for scenario,volume,mode,direction,enabled in [('up',12,0,1,1),('down',12,0,-1,1),('maximum',30,0,1,1),('minimum',0,0,-1,1),('avls',16,0,1,1),('preset',12,1,1,1),('fixed',12,0,1,0),('apply-error',12,0,1,1),('wrong-thread',12,0,1,1),('uninitialized',12,0,1,1),('wrong-image',12,0,1,1),('changed-code',12,0,1,1)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for data in (stock,program):
  elf=ELFFile(io.BytesIO(data))
  for segment in elf.iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   start=int(segment['p_vaddr']);base=start&~4095;size=(start-base+int(segment['p_memsz'])+4095)&~4095
   u.mem_map(base,size);u.mem_write(start,segment.data())
 u.mem_map(stack,65536);u.mem_map(context,4096);u.mem_map(done,4096)
 def put(a,value):u.mem_write(a,struct.pack('<I',value&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x612c48,0 if scenario=='uninitialized' else 1);put(0xe171ac,1);put(0xe17310,mode);put(0xe17314,volume);put(0xe17318,1)
 for i,value in enumerate((8,15,22)):put(0xe1731c+i*4,value)
 put(0xe17328,scenario=='avls');put(0x612c58,16);put(symbols['xw_test_loaded'],scenario!='wrong-image');u.mem_write(output,b'\x5a'*20)
 if scenario=='changed-code':u.mem_write(0x326d00,bytes([stock[0x326d00-0x8000]^1]))
 calls=[];depth=[0]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  if pc==0x326ea0:uc.reg_write(UC_ARM_REG_R0,enabled);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc in (0xdc1c,0xe2c4):
   assert uc.reg_read(UC_ARM_REG_R0)==0xe15f6c;depth[0]+=1 if pc==0xdc1c else -1;assert 0<=depth[0]<=1;uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0x327964:
   calls.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,7 if scenario=='apply-error' else 0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(register,value&0xffffffff)
  u.emu_start(symbols[name],done+4,count=20000000);assert u.reg_read(UC_ARM_REG_PC)==done,(scenario,name);assert not depth[0];return signed(u.reg_read(UC_ARM_REG_R0))
 bound=call('xw_stock_volume_bind',context)
 if scenario in ('wrong-image','changed-code'):
  assert bound==-3 and not calls;results.append(dict(case=scenario,bind=bound));continue
 assert bound==0
 if scenario=='wrong-thread':put(symbols['xw_test_thread'],18)
 read_result=call('xw_stock_volume_read',context,output)
 if scenario in ('wrong-thread','uninitialized'):
  assert read_result==(-4 if scenario=='wrong-thread' else -2) and bytes(u.mem_read(output,20))==b'\x5a'*20;results.append(dict(case=scenario,read=read_result));continue
 assert read_result==0;view=struct.unpack('<5I',u.mem_read(output,20));assert view[2]==(30 if not enabled else 2 if mode else 30)
 rc=call('xw_stock_volume_step',context,direction)
 if scenario=='fixed':assert rc==-3 and not calls
 elif scenario=='apply-error':assert rc==-9 and get(0xe17314)==13 and calls==[13]
 else:
  assert rc==1 and len(calls)==1
  expected={'up':13,'down':11,'maximum':30,'minimum':0,'avls':16,'preset':22}[scenario];assert get(0xe17314)==expected and calls==[expected],(scenario,get(0xe17314),calls)
  if scenario=='preset':assert get(0xe17318)==2
 results.append(dict(case=scenario,result=rc,native_manual=get(0xe17314),hardware_apply=calls))
report=dict(passed=True,native_binding=True,original_audioc_instructions=True,physical_device_accessed=False,cases=results,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_image.h','runtime/platform/player/stock_volume.h','tools/test_stock_volume_host.py']},limits=['Loader identity, selected output mode, mutexes and hardware application are modeled.','Original guarded binding and AudioC step/get/mode instructions execute.','An installed in-process host service is still required; no independent SDK-client endpoint or hardware acceptance is established.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
