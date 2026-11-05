"""Original command3 completion through Moma-finalize thunks; callee effects modeled."""
import hashlib,io,json,struct,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
path=ROOT/'work/targets-jp/SpiderApp';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));rows=[]
def word(address):
 segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address<address+4<=s['p_vaddr']+s['p_filesz'])
 return struct.unpack_from('<I',raw,int(segment['p_offset']+address-segment['p_vaddr']))[0]
outer=word(0x275c84);counter=word(0x275c80)
leaves={word(outer+i*12+8) for i in range(4)} | {word(0x60f71c+i*12+8) for i in range(15)}
profiles=[(3,*p) for p in ((0,False,0),(1,False,0),(0,True,1),(1,True,1),(0,True,2),(1,True,2))]+[(6,1,True,1),(7,1,True,1)]
for command,ready,chain,initial in profiles:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 area=0x71000000;u.mem_map(area,65536);root=area;done=area+0xff00;calls=[];pool_calls=[];events=[]
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 put(root+4,command);put(root+0x4c,ready);put(root+0x1c,area+0x1000);put(root+0x48,area+0x2000)
 if chain:put(counter,initial);put(0x822490,1)
 boundaries={0x3b0e0:'module-complete',0x50988:'service-complete',0x104fc:'root-flag',0x337dd4:'object-release',0x3ce08:'subsystem-get',0x3cdd0:'subsystem-release',0x288100:'moma-manager-release',0x28babc:'MomaLcPluginLib_finalize',0x2958a8:'MomaLib_finalize',0xa55b8:'queue-finalize',0x3365d4:'ticket-destroy',0x3378f4:'mutex-release',0xed94:'client-finalize',0xed98:'client-state-finalize',0xb6888:'input-get',0xb6b1c:'input-release',0xb6b18:'input-release-secondary'}
 boundaries.update({0x10e68:'command-notify',0x140b4:'gui-resume-boundary'})
 def hook(cpu,pc,size,context):
  if pc==done:cpu.emu_stop();return
  if pc==0xa57f0:
   events.append(cpu.reg_read(UC_ARM_REG_R0));cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
  if chain and pc in (0x275cbc,0x275dcc):
   calls.append(dict(address=hex(pc),name='pool-table' if pc==0x275cbc else 'pool-finalizer'));return
  if chain and pc==0x285f94:
   pool_calls.append(cpu.reg_read(UC_ARM_REG_R0));calls.append(dict(address=hex(pc),name='pool-release'))
  elif chain and pc in leaves:pass
  elif pc in boundaries:
   calls.append(dict(address=hex(pc),name=boundaries[pc]))
   if chain and pc==0xb6b18:return
  elif pc not in (0xff5c,0x33b83c):return
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 def interrupt(*args):raise AssertionError('Unexpected native system instruction')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,interrupt)
 u.reg_write(UC_ARM_REG_R0,root);u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
 try:u.emu_start(0x10ee4,done+4,count=10000)
 except Exception as error:raise AssertionError((command,ready,hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),calls,events)) from error
 assert u.reg_read(UC_ARM_REG_PC)==done
 names=[c['name'] for c in calls]
 if command==3:assert names.index('moma-manager-release')<names.index('MomaLcPluginLib_finalize')<names.index('MomaLib_finalize')<names.index('queue-finalize')
 else:assert names==([] if command==6 else ['command-notify','gui-resume-boundary']) and events==[0x41000a if command==6 else 0x410009]
 if chain:
  reached='input-release-secondary' in names
  assert pool_calls==([0x822494] if reached and initial==1 else [])
  assert struct.unpack('<I',u.mem_read(0x822490,4))[0]==(0 if pool_calls else 1)
  assert struct.unpack('<I',u.mem_read(counter,4))[0]==initial-int(reached)
  if pool_calls:assert names.index('MomaLib_finalize')<names.index('input-release-secondary')<names.index('pool-finalizer')<names.index('pool-release')<names.index('queue-finalize')
 rows.append(dict(command=command,root_ready_fixture=ready,pool_chain_executed=chain,initial_met_reference=initial,pool_release_arguments=[hex(a) for a in pool_calls],calls=calls,queued_events=[hex(e) for e in events]))
out=ROOT/'work/player-finalize-order'/str(time.time_ns());out.mkdir(parents=True)
report=dict(passed=True,original_completion_and_finalizer_instructions=True,native_moma_thunks_executed=True,subsystem_finalization_effects_modeled=True,device_accessed=False,cases=rows,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,__import__('pathlib').Path(__file__))},limits=['Command3 completion state supplied; pending-worker coordination before entry is not executed.','Native completion dispatcher,10d80 finalizer and Moma branch thunks execute; target cleanup effects are intercepted.','No proof of object lifetimes, actual thread drain, process exit or a safe postponement hook.'])
report['limits'].append('Combined pool profiles execute the secondary input thunk, reference decrement, nested reverse dispatch and pool flag reset; other cleanup leaves and pool release effects remain intercepted. Initial native references and root-ready state are fixtures.')
report['limits'].append('Command6/7 profiles enter completion directly with completed preparation supplied; command-notify and GUI-resume boundaries are intercepted. No live-controller preservation or full background playback claim.')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
