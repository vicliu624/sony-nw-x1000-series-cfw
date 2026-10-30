"""ARM client -> private stock provider -> original AudioC integration, PC only."""
from pathlib import Path
import hashlib, io, json, struct, subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-provider';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/client.c','runtime/platform/player/stock_provider.c','runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_gui.c','runtime/platform/player/stock_volume.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/stock_provider_host.c']
artifact=work/'consumer.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
helper=artifact.read_bytes();elf=ELFFile(io.BytesIO(helper));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
cases=[]
for scenario in ('normal','apply-error','wrong-image','partial-bind','partial-info-bind','track-change','state-change','chapterless-states'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for raw in (stock,helper):
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 stack,done,area=0x70000000,0x72000000,0x71000000;u.mem_map(stack,65536);u.mem_map(done,4096);u.mem_map(area,65536)
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x612c48,1);put(0xe171ac,1);put(0xe17310,0);put(0xe17314,12)
 put(symbols['xw_test_loaded'],scenario!='wrong-image')
 if scenario=='partial-bind':u.mem_write(0x326d00,bytes([stock[0x326d00-0x8000]^1]))
 if scenario=='partial-info-bind':u.mem_write(0x275e00,bytes([stock[0x275e00-0x8000]^1]))
 handle,controller,session,data,info,owned,track,chapter,payload,id_object,impl=(area+x for x in (0x1000,0x2000,0x4000,0x5000,0x6000,0x7000,0x8000,0x9000,0xa000,0xb000,0xc000))
 has_track=scenario in ('track-change','state-change','chapterless-states')
 has_state=scenario in ('state-change','chapterless-states')
 if has_track:
  put(0x6922d8,handle);put(handle,controller);put(handle+4,7);put(controller+0xec8+0x118,session)
  put(session+8,1);put(session+12,1);put(session+20,7);put(session+28,data)
  put(data,2);put(data+4,info);put(0x835de8,1);put(0x838744,3);put(0x822934,4)
  put(info+4,1);put(info+96,track);put(info+100,chapter);put(track,0x49a89c);put(track+4,1);put(track+8,payload);put(chapter,1)
  put(payload+4,id_object);put(id_object,0x60fc60);put(id_object+4,impl);put(impl,1);put(impl+8,0x123)
  if scenario=='chapterless-states':put(info+100,0)
 actor=area+0xd000
 if has_state:
  put(0x6831dc,actor);u.mem_write(actor,b'\2\2');put(actor+4,0x3f11d8);u.mem_write(actor+8,b'\xff\xff');u.mem_write(actor+13,b'\2')
 applied=[];depth=[0];info_locks={1:0,2:0,3:0,4:0};live=[False];allocations=[0];frees=[0];fail_info=[False]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if pc==0x326ea0:finish(1);return
  if pc in (0xdc1c,0xe2c4):
   assert uc.reg_read(UC_ARM_REG_R0)==0xe15f6c;depth[0]+=1 if pc==0xdc1c else -1;assert 0<=depth[0]<=1;finish();return
  if pc==0x327964:applied.append(uc.reg_read(UC_ARM_REG_R0));finish(7 if scenario=='apply-error' else 0)
  if pc in (0x335788,0x3357e4):
   mutex=uc.reg_read(UC_ARM_REG_R0);assert mutex in info_locks;info_locks[mutex]+=1 if pc==0x335788 else -1;assert 0<=info_locks[mutex]<=1;finish();return
  if pc==0x286028:
   assert uc.reg_read(UC_ARM_REG_R0)==0x822494 and not live[0]
   if fail_info[0]:finish();return
   live[0]=True;allocations[0]+=1;finish(owned);return
  if pc==0x286058:
   assert uc.reg_read(UC_ARM_REG_R1)==owned and live[0] and get(track+4)==1 and get(chapter)==1;live[0]=False;frees[0]+=1;finish();return
  if pc==0xd85c:
   dst,src,n=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2));assert n==0x5c;uc.mem_write(dst,bytes(uc.mem_read(src,n)));finish(dst);return
  if pc in (0x285d24,0x33d8c0,0x33b83c):finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value&0xffffffff)
  u.emu_start(symbols[name],done+4,count=30000000);assert u.reg_read(UC_ARM_REG_PC)==done and depth[0]==0 and not any(info_locks.values()) and not live[0] and allocations[0]==frees[0]
  value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
 rc=call('test_bind')
 if scenario in ('wrong-image','partial-bind','partial-info-bind'):
  assert rc==-3 and call('test_bound')==0 and call('test_bindings_remaining')==0 and not applied
  assert call('test_poll')==-7
  cases.append(dict(case=scenario,bind=rc));continue
 assert rc==0 and call('test_bind')==-4
 expected_valid=35 if has_state else 34 if has_track else 32
 assert call('test_poll')==0 and call('test_valid')==expected_valid and call('test_state')==(2 if has_state else 0) and call('test_volume')==12
 assert get(symbols['test_changes'])&96==96
 assert call('test_poll')==0 and get(symbols['test_changes'])==0
 if scenario=='track-change':
  assert bytes(u.mem_read(call('test_track_id'),65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=123'
  put(impl+8,0x456)
  assert call('test_poll')==0 and get(symbols['test_changes'])==2
  assert bytes(u.mem_read(call('test_track_id'),65)).split(b'\0')[0]==b'moma-object:MOMA_LC;domain=FOLDERTREE;type=MEDIA;id=456'
  fail_info[0]=True
  assert call('test_poll')==0 and call('test_valid')==32 and get(symbols['test_changes'])==2
  assert bytes(u.mem_read(call('test_track_id'),65))==bytes(65)
  fail_info[0]=False
  assert call('test_poll')==0 and call('test_valid')==34 and get(symbols['test_changes'])==2
  put(info+96,0)
  assert call('test_poll')==0 and call('test_valid')==32 and get(symbols['test_changes'])==2
  put(info+96,track)
  assert call('test_poll')==0 and call('test_valid')==34 and get(symbols['test_changes'])==2
 if has_state:
  transitions=[
   # primary, substate, error, GUI mode/state, bound objects, observed state, mask
   (0,0,0,2,2,1,0,1), # controller and GUI disagree
   (0,0,0,1,4,1,0,0), # original GUI is still starting
   (0,0,0,1,5,1,3,1), # both sources agree on stable playback
   (0,1,0,1,5,1,0,1), # native controller pending despite a stable GUI
   (0,0,0,1,5,1,3,1),
   (0,0,7,1,5,1,0,1), # native error must not remain PLAYING
   (0,0,0,1,5,1,3,1),
   (2,0,0,1,1,1,1,1), # stopped target plus inactive original component
   (0,0,0,1,5,0,0,3), # default target0 and stale GUI cannot create playback
   (1,0,0,2,2,1,2,3),
  ]
  for primary,substate,error,mode,phase,objects,state,mask in transitions:
   put(info+4,primary);put(info+8,substate);put(info+12,error);u.mem_write(actor,bytes((mode,phase)))
   put(info+96,track if objects else 0);put(info+100,chapter if objects and scenario!='chapterless-states' else 0)
   assert call('test_poll')==0 and call('test_state')==state and get(symbols['test_changes'])==mask,(primary,substate,error,mode,phase,objects)
   assert call('test_valid')==(32|(2 if objects else 0)|(1 if state else 0))
  u.mem_write(actor+8,b'\0\0')
  assert call('test_poll')==0 and call('test_valid')==34 and call('test_state')==0 and get(symbols['test_changes'])==1
  u.mem_write(actor+8,b'\xff\xff')
  assert call('test_poll')==0 and call('test_valid')==35 and call('test_state')==2 and get(symbols['test_changes'])==1
 rc=call('test_command',5,1);assert rc==(-9 if scenario=='apply-error' else 1)
 # A command result never fabricates the last observed snapshot.
 assert call('test_volume')==12 and applied==[13]
 assert call('test_poll')==0 and call('test_volume')==13 and get(symbols['test_changes'])==32
 assert call('test_command',4,20)==-3 and call('test_command',5,2)==-1 and applied==[13]
 put(symbols['xw_test_thread'],18)
 assert call('test_poll')==-4 and call('test_volume')==13
 assert call('test_command',5,1)==-4 and call('test_close')==-4 and call('test_bound')==1
 put(symbols['xw_test_thread'],17)
 assert call('test_poll')==0 and get(symbols['test_changes'])&64
 assert call('test_close')==0 and call('test_bound')==0 and call('test_poll')==-7
 assert call('test_bindings_remaining')==0
 cases.append(dict(case=scenario,command_result=rc,applied=applied,volume_notification=True,track_notification=has_track,state_notification=has_state,unobserved_fields_unknown=True))
report=dict(passed=True,device_accessed=False,actual_client_core=True,actual_stock_provider=True,original_audioc=True,original_ctrlinfo=True,cases=cases,
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_provider.h','tools/fixtures/stock_host_image.c','tools/test_stock_provider.py']},
 limits=['Loaded-image identity, output-mode selection, mutexes, CtrlInfo pool allocation/free, memcpy, error logging and hardware application are modeled.',
         'Transport GUI adapters are covered by test_stock_gui_host.py; this integration fixture exercises native volume, CtrlInfo/local-media identity and observation lifecycle.',
         'Control snapshots, actor states and output mode are synthetic fixture inputs; no audio output or device sleep/USB qualification is established.',
         'No process transport, service bootstrap or metadata/media backend is installed.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
