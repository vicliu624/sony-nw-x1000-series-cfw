"""PC-only original ARM instruction replay with synthetic model/NVP reads.

Stops before unrelated runtime setup. All imported calls and interrupts are
blocked except explicitly modelled open/read/close/memcpy; no host NVP IO.
"""
from pathlib import Path
import hashlib,io,json,struct
import unicorn
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];data=(ROOT/'work/targets-jp/Responder').read_bytes()
digest=hashlib.sha256(data).hexdigest();assert digest=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
segments=[s for s in ELFFile(io.BytesIO(data)).iter_segments() if s['p_type']=='PT_LOAD']
def cstring(u,address,count=96):return bytes(u.mem_read(address,count)).split(b'\0',1)[0].decode('ascii')
def word(u,address):return struct.unpack('<I',u.mem_read(address,4))[0]
vectors=[(0x05000004,4,'NW-X1050',0),(0x05000005,4,'NW-X1060',0),
 (0x05020004,4,'NWZ-X1050',1),(0x05020005,4,'NWZ-X1060',1),
 (0x05040004,4,'NWZ-X1051',1),(0x05040005,4,'NWZ-X1061',1),
 (0x05000005,3,'NWZ-X1050',1)]
rows=[]
for supplied,read_bytes,expected,expected_flag in vectors:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
 for segment in segments:u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 u.mem_write(0x562b90,bytes(4));phase='read';selected_model=0;stops=[];imports=[]
 def hook(uc,pc,size,context):
  if pc==0x147f0 and phase!='read':
   uc.reg_write(UC_ARM_REG_R0,selected_model);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0xbff0:
   assert phase=='read' and cstring(uc,uc.reg_read(UC_ARM_REG_R0))=='/dev/icx1087_nvp/16' and uc.reg_read(UC_ARM_REG_R1)==2
   imports.append('simulated open flags=O_RDWR');uc.reg_write(UC_ARM_REG_R0,7)
  elif pc==0xc2e4:
   assert phase=='read' and uc.reg_read(UC_ARM_REG_R0)==7 and uc.reg_read(UC_ARM_REG_R2)==4
   uc.mem_write(uc.reg_read(UC_ARM_REG_R1),struct.pack('<I',supplied)[:read_bytes]);uc.reg_write(UC_ARM_REG_R0,read_bytes);imports.append('simulated read')
  elif pc==0xb90c:
   assert phase=='read' and uc.reg_read(UC_ARM_REG_R0)==7;uc.reg_write(UC_ARM_REG_R0,0);imports.append('simulated close')
  elif pc==0xba14:
   dst=uc.reg_read(UC_ARM_REG_R0);src=uc.reg_read(UC_ARM_REG_R1);count=uc.reg_read(UC_ARM_REG_R2)
   assert phase=='config_copy' and dst==0x6afb94 and src==0x562b94 and count==76
   uc.mem_write(dst,bytes(uc.mem_read(src,count)));uc.reg_write(UC_ARM_REG_R0,dst);imports.append('simulated memcpy 76 bytes')
  elif pc in (0x14548,0x187ce4,0x17dc30,0x17dca4):
   stops.append(pc);uc.emu_stop();return
  elif 0xb700<=pc<0xc314:raise RuntimeError(f'Unexpected imported call {pc:#x}')
  else:return
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def interrupt(*args):raise RuntimeError('Unexpected syscall/interrupt')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,interrupt)
 def call(address):
  u.reg_write(UC_ARM_REG_SP,0x6001f000);u.reg_write(UC_ARM_REG_LR,0x50000000);u.emu_start(address,0x50000000,count=10000)
 call(0x147f0);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 selected_model=u.reg_read(UC_ARM_REG_R0);assert selected_model==(supplied if read_bytes==4 else 0x05020004)
 phase='model_prefix';call(0x1447c);assert stops==[0x14548]
 name=cstring(u,0x562b94,16);flag=word(u,0x562b94+56);assert name==expected and flag==expected_flag
 phase='config_copy';u.reg_write(UC_ARM_REG_R0,0x562b94);call(0x17d618)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and word(u,0x6afb90)==0x6afb94 and word(u,0x6afb94+56)==flag
 phase='path_default';refcount=word(u,0x187d7c);u.mem_write(refcount,bytes(4));call(0x187c6c)
 assert stops[-1]==0x187ce4 and cstring(u,0x6b8058,32)=='/contents/MTPDB.dat'
 phase='path_override';u.reg_write(UC_ARM_REG_R0,0x60001000);call(0x17dc04)
 selected=cstring(u,0x6b8058,32);assert selected==('/db/MTPDB.dat' if flag else '/contents/MTPDB.dat')
 assert stops[-1]==(0x17dc30 if flag else 0x17dca4)
 rows.append({'synthetic_nvp_word':f'{supplied:#010x}','synthetic_read_bytes':read_bytes,'reader_result':f'{selected_model:#010x}',
  'model_label':name,'selector_0x38':flag,'path_after_replayed_setup':selected,'stop_addresses':[hex(v) for v in stops],'modelled_imports':imports})
report={'passed':True,'scope':'original ARM model-reader/profile-prefix/config-copy/path-branch instruction replay',
 'stock_process_started':False,'stock_instructions_emulated':True,'device_accessed':False,'real_nvp_read':False,'real_nvp_modified':False,'database_opened':False,
 'responder_sha256':digest,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'unicorn_version':unicorn.__version__,
 'cases':rows,'limits':['All NVP bytes and read lengths are synthetic; no connected device model asserted.',
 'Profile replay stops at 0x14548 before later environment/metadata setup; no complete boot or scan executed.',
 'Configuration copy and first path initialization are sequenced explicitly; actual startup order is not proven by replay.',
 'This qualifies one path buffer and its selector, not every database write or the separate /db descriptor.',
 'The stock reader uses O_RDWR; it is never invoked against hardware by this tool.']}
(ROOT/'sources/native-stock-db-model-selection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'stock_process_started':False,'device_accessed':False,'cases':[{k:v for k,v in row.items() if k not in ('stop_addresses','modelled_imports')} for row in rows]},indent=2))
