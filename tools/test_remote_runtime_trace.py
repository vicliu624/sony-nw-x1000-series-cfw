"""Actual remote_auto ARM branch after the native Settings pump consumed intent."""
import argparse,hashlib,io,json,re,struct,subprocess,tempfile,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-review',required=True);p.add_argument('--historical',action='store_true',help='Replay a retained exact artifact without declaring its old sources current');args=p.parse_args()
if args.historical:path=ROOT/args.host_review;review=json.loads(path.read_text())
else:path,review=receipt(args.host_review)
library=path.parent/'libx1000-player-analysis.so';assert digest(library)==review['library_sha256']
elf=ELFFile(io.BytesIO(library.read_bytes()));syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']!='STT_FILE'}
origin='';factory=None
for s in elf.get_section_by_name('.symtab').iter_symbols():
 if s['st_info']['type']=='STT_FILE':origin=s.name
 elif origin=='remote_auto.c' and s.name=='factory':factory=s['st_value']
assert factory
latest_build=review.get('library_compile',{}).get('remote_trace_build')
child_detail='trace_child_generation' in syms
fields={'initialized':'initialized','held':'held','phase':'backend.phase','pending':'backend.pending_enabled','ready':'backend.process.service_ready',
        'child':'backend.process.child','reaped':'backend.process.reaped','pair_owner':'pairing.owner','pair_reaped':'pairing.reaped','store_child':'pairing_store_job.child'}
if latest_build:
 fields.update(start_serial='backend.last_start.serial', start_generation='backend.last_start.generation',
               start_stage='backend.last_start.stage', start_result='backend.last_start.result')
if child_detail:
 fields.update(start_reaped='backend.last_start.child_reaped')
with tempfile.TemporaryDirectory(dir=ROOT/'work',prefix='runtime-trace-layout-') as folder:
 c=Path(folder)/'layout.c';obj=Path(folder)/'layout.o'
 c.write_text(('#define WR_PAIRING_TRACE\n' if 'wr_start_failure_capture' in syms else '')+
              '#define WR_PAIRING_PROCESS\n#include <stddef.h>\n#include "runtime/apps/wireless-remote/settings_factory.h"\n'
              '#include "runtime/platform/player/parent_trace_store.h"\n'
              '#include "runtime/apps/wireless-remote/retirement_log.h"\n'
              'char store_initialized[offsetof(struct xw_parent_trace_store,initialized)+1];\n'
              'char packet_operation[offsetof(struct wr_start_failures,packet_operation)+1];\n'
              'char packet_result[offsetof(struct wr_start_failures,packet_result)+1];\n'
              +''.join(f'char {name}[offsetof(struct wr_settings_factory,{field})+1];\n' for name,field in fields.items()))
 subprocess.run(['arm-linux-gnueabi-gcc','-c','-I',str(ROOT),str(c),'-o',str(obj)],check=True)
 e=ELFFile(io.BytesIO(obj.read_bytes()));offsets={s.name:s['st_size']-1 for s in e.get_section_by_name('.symtab').iter_symbols()
     if s.name in fields or s.name in ('store_initialized','packet_operation','packet_result')}
page=json.loads((path.parent/'remote-page/report.json').read_text());native=ROOT/page['artifact'];assert digest(native)==page['sha256'];stock=ELFFile(io.BytesIO(native.read_bytes()))
rows=[]
dis=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(library)],text=True)
plt={name:int(at,16) for at,name in re.findall(r'^([0-9a-f]+) <(\w+)@plt>:',dis,re.M)}
for blocker in ('remote-child','pairing-child','store-child','activation-pending','off'):
 phase,held=(1,0) if blocker=='off' else (2,1)
 expected=[] if blocker=='off' else [1,17,18]
 cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.mem_map(0x8000,0x1000000);base=0x50000000;cpu.mem_map(base,0x400000);area=0x70000000;cpu.mem_map(area,0x10000);stop=area+0xff00
 for image,relocation in ((stock,0),(elf,base)):
  for seg in image.iter_segments():
   if seg['p_type']=='PT_LOAD':cpu.mem_write(relocation+seg['p_vaddr'],seg.data())
 put=lambda a,v:cpu.mem_write(a,struct.pack('<I',v));get=lambda a:struct.unpack('<I',cpu.mem_read(a,4))[0]
 for name,value in (('initialized',1),('held',held),('phase',phase),('pending',0),('ready',1)):
  put(base+factory+offsets[name],value)
 blocked_field={'remote-child':'child','pairing-child':'pair_owner','store-child':'store_child','activation-pending':'pending'}.get(blocker)
 if blocked_field:put(base+factory+offsets[blocked_field],1234 if blocked_field!='pending' else 1)
 stores=[]
 if latest_build:
  put(base+syms['trace_process_id'], 0x24681357)
  put(base+factory+offsets['start_serial'], 41)
  put(base+factory+offsets['start_generation'], 43)
  put(base+factory+offsets['start_stage'], 4)
  put(base+factory+offsets['start_result'], (-6)&0xffffffff)
  if child_detail:
   put(base+factory+offsets['start_reaped'],1)
   put(base+syms['trace_child_generation'],43)
   put(base+syms['trace_child_log']+offsets['packet_operation'],1)
   put(base+syms['trace_child_log']+offsets['packet_result'],(-5)&0xffffffff)
 models={base+syms[n]:v for n,v in [('xw_player_host_original_exiting',0),('xw_player_remote_state_active',1),('xw_player_host_wireless_player_active',1),('wr_settings_factory_tick',0),('xw_player_host_remote_idle',0)]}
 def hook(uc,pc,size,unused):
  if pc==stop:uc.emu_stop();return
  a,b=uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)
  if pc==base+plt['memcpy']:
   uc.mem_write(a,bytes(uc.mem_read(b,uc.reg_read(UC_ARM_REG_R2))));value=a
  elif pc==base+plt['memset']:
   uc.mem_write(a,bytes([b&255])*uc.reg_read(UC_ARM_REG_R2));value=a
  elif pc==base+syms['xw_parent_trace_store_init']:
   stores.append(('init',));put(a+offsets['store_initialized'],1);value=0
  elif pc==base+syms['xw_parent_trace_store_snapshot']:
   data=uc.reg_read(UC_ARM_REG_R2);seq=uc.reg_read(UC_ARM_REG_R3)
   capture=[(i+1,get(seq+4*i)) for i in range(31) if b&(1<<i)]
   if latest_build:
    assert get(uc.reg_read(UC_ARM_REG_SP))==((1<<27)|(1<<28) if child_detail else 28)
    if b&(1<<27):
     fields28=struct.unpack('<12I',uc.mem_read(data+27*48,48))
     stores.append(('latest',fields28))
    if child_detail and b&(1<<28):
     stores.append(('child',struct.unpack('<12I',uc.mem_read(data+28*48,48))))
    capture=[row for row in capture if row[0]!=28 and (not child_detail or row[0]!=29)]
   stores.append(('snapshot',capture));value=0
  elif pc in models:value=models[pc]
  else:return
  uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 cpu.hook_add(UC_HOOK_CODE,hook);cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
 try:cpu.emu_start(base+syms['xw_player_host_remote_auto'],stop+4,count=1000000)
 except Exception as e:raise AssertionError((blocker,hex(cpu.reg_read(UC_ARM_REG_PC)),hex(cpu.reg_read(UC_ARM_REG_LR)))) from e
 expected_identity=(0xfffffffa,4,int(child_detail),0,41,0,43,0,0x24681357,0,
                    int(latest_build or '0',16)&0xffffffff,int(latest_build or '0',16)>>32)
 latest_entries=[('latest',expected_identity)] if latest_build else []
 if child_detail:
  latest_entries.append(('child',(*expected_identity[4:],1,0xfffffffb,0,0)))
 assert cpu.reg_read(UC_ARM_REG_PC)==stop,(blocker,stores)
 assert stores==([('init',),*latest_entries,('snapshot',[])]
                 if blocker=='off' and latest_build else []),(blocker,stores)
 mask=get(base+syms['trace_pending'])
 stages=[i+1 for i in range(31) if mask&(1<<i)]
 assert stages==expected,(blocker,stages,expected)
 if blocker!='off':
  # A second live-owner iteration must remain memory-only, including init.
  cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
  cpu.emu_start(base+syms['xw_player_host_remote_auto'],stop+4,count=1000000)
  assert cpu.reg_read(UC_ARM_REG_PC)==stop and not stores,(blocker,stores)
  # A reaped supervisor's result must reach disk even if RF release is pending.
  stopping = blocker == 'remote-child' and child_detail and not args.historical
  for name,value in (('held',int(stopping)),('phase',3 if stopping else 1),('pending',0),
                     ('child',1234 if stopping else 0),('reaped',int(stopping)),
                     ('pair_owner',0),('store_child',0),('ready',0)):
   put(base+factory+offsets[name],value)
  cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
  cpu.emu_start(base+syms['xw_player_host_remote_auto'],stop+4,count=1000000)
  expected=[('init',),*latest_entries]+[
      ('snapshot',[(1,1),(17,2),(18,3)])]
  assert cpu.reg_read(UC_ARM_REG_PC)==stop and stores==expected,(blocker,stores)
  assert not get(base+syms['trace_pending'])
  if stopping:
   put(base+factory+offsets['held'],0)
   put(base+factory+offsets['phase'],1)
 if latest_build:
  stores.clear()
  for serial in (41,42):
   put(base+factory+offsets['start_serial'],serial)
   if child_detail and serial==42:
    put(base+factory+offsets['start_generation'],44)
   cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
   cpu.emu_start(base+syms['xw_player_host_remote_auto'],stop+4,count=1000000)
   assert cpu.reg_read(UC_ARM_REG_PC)==stop
   if serial==41:assert not stores
  second_identity=(*expected_identity[:4],42,0,44 if child_detail else 43,*expected_identity[7:])
  assert stores==[('latest',second_identity),('snapshot',[])],(blocker,stores)
 rows.append(dict(blocker=blocker,stages=stages,no_live_file_io=True,quiescent_batch=bool(stores)))
folder=ROOT/'work/remote-runtime-trace-tests'/str(time.time_ns());folder.mkdir(parents=True)
report=dict(passed=True,actual_remote_auto_arm=True,model_factory_tick_and_native_state=True,device_accessed=False,cases=rows,
 library_sha256=digest(library),host_review=str(path.relative_to(ROOT)),source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_remote_runtime_trace.py','runtime/platform/player/remote_auto.c','runtime/apps/wireless-remote/settings_factory.h']},
 limits=['Actual ARM runtime trace capture and flush gating execute; native ownership/factory progress and file backend are modeled.','The separate parent trace store suite executes the batch writer; no physical sleep, radio link or user-storage write is executed.'])
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
