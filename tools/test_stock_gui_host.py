"""Strict stock GUI query binding executing the original FSM and receivers."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-gui-host';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/client.c','runtime/platform/player/stock_provider.c','runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_volume.c','runtime/platform/player/stock_gui.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/stock_provider_host.c'];artifact=work/'profile.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
stock_elf=ELFFile(io.BytesIO(stock));ticket_cancel=next(s['st_value'] for section in stock_elf.iter_sections() if section['sh_type'] in ('SHT_SYMTAB','SHT_DYNSYM') for s in section.iter_symbols() if s.name=='PltTicket_cancel')
program=artifact.read_bytes();elf=ELFFile(io.BytesIO(program));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
stack,context,output,actor,done=0x70000000,0x71000000,0x71000100,0x71001000,0x72000000;cases=[]
matrix=[(f'mode-{mode}-state-{state}',mode,state) for mode,count in ((1,10),(2,7)) for state in range(1,count+1)]
scenarios=[(name,1,5) for name in ['active','inactive','no-actor','unready-state','unwritten','filtered','handler-busy','wrong-thread','wrong-image','changed-code']]+matrix
scenarios += [(f'skip-{direction}-m{mode}-{failure}',mode,state) for direction in ('next','previous') for mode,state in ((1,5),(2,2)) for failure in ('accepted','allocation','same-ticket','filtered','transition','no-controller')]
scenarios += [(f'transport-{operation}-m{mode}-{failure}',mode,state) for operation,mode,state in (('pause',1,5),('play',2,2)) for failure in ('accepted','allocation','same-ticket','filtered','transition','no-controller')]
scenarios += [('transport-play-m1-already',1,5),('transport-pause-m2-already',2,2)]
scenarios += [('skip-next-m1-provider',1,5),('skip-previous-m2-provider',2,2),('transport-play-m2-provider',2,2),('transport-pause-m1-provider',1,5)]
scenarios += [('view-active',1,5),('view-paused',2,2),('view-inactive',1,1),('view-shifted-state',1,5),('view-switched-actor',1,5)]
for scenario,mode,state in scenarios:
 is_transport=scenario.startswith('transport-');is_skip=scenario.startswith('skip-') or is_transport;direction=1 if '-next-' in scenario else -1
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for data in (stock,program):
  image=ELFFile(io.BytesIO(data))
  for segment in image.iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   start=int(segment['p_vaddr']);base=start&~4095;size=(start-base+int(segment['p_memsz'])+4095)&~4095;u.mem_map(base,size);u.mem_write(start,segment.data())
 u.mem_map(stack,65536);u.mem_map(context,65536);u.mem_map(done,4096)
 def put(address,value):u.mem_write(address,struct.pack('<I',value&0xffffffff))
 def get(address):return struct.unpack('<I',u.mem_read(address,4))[0]
 put(0x6831dc,0 if scenario=='no-actor' else actor);u.mem_write(actor,b'\1'+(b'\0' if scenario=='unready-state' else b'\x0a' if scenario=='unwritten' else b'\1' if scenario=='inactive' else b'\5'));put(actor+4,0x3f11d8);u.mem_write(actor+13,b'\2');u.mem_write(actor+8,struct.pack('<H',7 if scenario=='handler-busy' else 0xffff));put(output,0x5a5a5a5a)
 if scenario.startswith(('mode-','view-')):u.mem_write(actor,bytes((mode,state)))
 callbacks=set();allocations=[];lower=[]
 if is_skip:
  u.mem_write(actor,bytes((mode,1 if scenario.endswith('-transition') else state)))
  put(0x6922d8,0 if scenario.endswith('-no-controller') else context+0x3000)
  put(0x6922d8+0x10,7 if scenario.endswith('-same-ticket') else 6)
  put(context+0x3000,context+0x4000);put(context+0x3004,0x1234)
  put(context+0x4010,6);put(context+0x402c,context+0x4028)
  # UI entry/exit work is modeled, but the event handler, controller API,
  # payload construction and native queue admission execute original code.
  for descriptor,count in ((0x3f1604,10),(0x3f11e0,7)):
   for offset in (20,24):
    table=get(descriptor+offset)
    if table:
     callbacks.update(get(table+4*s) for s in range(count) if get(table+4*s))
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario=='changed-code':u.mem_write(0x17c410,b'\x01')
 receiver=[]
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  def finish(value=0):uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  if (scenario=='filtered' or scenario.endswith('-filtered')) and pc==0x50078:finish();return
  if is_skip:
   if pc in (0x27dacc,0x27db98,0x27d6a0):
    lower.append(pc)
    if is_transport:assert uc.reg_read(UC_ARM_REG_R1)==(1 if '-play-' in scenario else 2)
   if pc==0x27c378:
    assert uc.reg_read(UC_ARM_REG_R0)==context+0x4000
    kind=uc.reg_read(UC_ARM_REG_R2);assert kind==(0x12 if is_transport else 0x15 if direction==1 else 0x16);allocations.append(kind)
    if scenario.endswith('-allocation'):finish(0x2604);return
    put(context+0x500c,kind);put(uc.reg_read(UC_ARM_REG_R3),context+0x5000);finish();return
   if pc in (0x3c194,0xb6888,0x1542c):finish(context+0x6000);return
   if pc in callbacks or pc in (0x3cc14,0xb6b48,0x3cd34,0x116d4,0x33b83c,0x33b918,0x1764c,0x27d654,0x27d614,0x335788,0x3357e4,0x3354f4):finish();return
   # Resolve the original exported ticket primitive instead of a guessed address.
   if pc==ticket_cancel:finish();return
  if pc==0x17c608:
   values=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
   expected_request=0x440027 if is_transport else (0x440028 if direction==1 else 0x440029) if is_skip else 0x440019
   assert values[0]==actor and values[1]==expected_request
   assert values[3]==0;receiver.append(values)
   if scenario=='view-shifted-state':uc.mem_write(actor,b'\2\2')
   if scenario=='view-switched-actor':put(0x6831dc,actor+0x200)
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,*arguments):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),arguments):u.reg_write(reg,value&0xffffffff)
  u.emu_start(address,done+4,count=20000000);assert u.reg_read(UC_ARM_REG_PC)==done;result=u.reg_read(UC_ARM_REG_R0);return result if result<0x80000000 else result-0x100000000
 bound=call(symbols['test_bind']) if scenario.endswith('-provider') else call(symbols['xw_stock_gui_bind'],context)
 if scenario in ('wrong-image','changed-code'):assert bound==-3 and not receiver;cases.append(dict(case=scenario,bind=bound));continue
 assert bound==0
 if scenario.startswith('view-'):
  previous=bytes(u.mem_read(output,12))
  rc=call(symbols['xw_stock_gui_read'],context,output)
  if scenario in ('view-shifted-state','view-switched-actor'):assert rc==-4 and bytes(u.mem_read(output,12))==previous
  else:assert rc==0 and struct.unpack('<3I',u.mem_read(output,12))==(mode,state,int(scenario!='view-inactive'))
  cases.append(dict(case=scenario,result=rc,receiver_calls=len(receiver)))
  continue
 if is_skip:
  if scenario.endswith('-provider'):
   operation=(0 if '-play-' in scenario else 1) if is_transport else (2 if direction==1 else 3)
   rc=call(symbols['test_command'],operation,0)
  else:rc=call(symbols['xw_stock_gui_set_playing' if is_transport else 'xw_stock_gui_skip'],context,int('-play-' in scenario) if is_transport else direction)
  expected=-4 if scenario.endswith(('-filtered','-transition')) else -2 if scenario.endswith('-no-controller') else -9 if scenario.endswith(('-allocation','-same-ticket')) else 1
  assert rc==expected,(scenario,rc,lower,allocations)
  rejected=scenario.endswith(('-filtered','-transition','-no-controller','-already'))
  assert len(lower)==int(not rejected) and len(allocations)==int(not rejected)
  if not rejected:
   assert lower==[0x27d6a0 if is_transport else 0x27dacc if direction==1 else 0x27db98]
   expected_actor=(bytes((2,1)) if mode==1 else bytes((1,4))) if is_transport else bytes((mode,6 if mode==1 else 3))
   assert bytes(u.mem_read(actor,2))==expected_actor
   assert get(0x6922d8+0x10)==(0xffffffff if scenario.endswith('-allocation') else 7)
   assert struct.unpack('<H',u.mem_read(actor+8,2))[0]==0xffff
  if scenario.endswith('-already'):assert get(0x6922d8+0x10)==6 and bytes(u.mem_read(actor,2))==bytes((mode,state)) and not receiver
  if scenario.endswith('-provider'):assert call(symbols['test_close'])==0
  cases.append(dict(case=scenario,result=rc,receiver_calls=len(receiver),controller_calls=len(lower),allocations=len(allocations)))
  continue
 if scenario=='wrong-thread':put(symbols['xw_test_thread'],18)
 rc=call(symbols['xw_stock_gui_audio_active'],context,output)
 expected=(-2 if mode==1 and state==10 else 0) if scenario.startswith('mode-') else {'active':0,'inactive':0,'no-actor':-2,'unready-state':-2,'unwritten':-2,'filtered':-4,'handler-busy':-4,'wrong-thread':-4}[scenario];assert rc==expected,(scenario,rc)
 if rc:assert get(output)==0x5a5a5a5a
 else:assert get(output)==(int(mode==2 or state>=4) if scenario.startswith('mode-') else int(scenario=='active'))
 if scenario.startswith('mode-'):
  assert bytes(u.mem_read(actor,2))==bytes((mode,state))
  assert struct.unpack('<H',u.mem_read(actor+8,2))[0]==0xffff
  assert len(receiver)==1
 # Prove the stock wrapper's zero default is ambiguous in the missing-actor and
 # unwritten-output cases. The new binding refuses both instead of reporting idle.
 raw_value=None
 if scenario in ('no-actor','unwritten'):raw_value=call(0x18150,0);assert raw_value==0
 cases.append(dict(case=scenario,result=rc,receiver_calls=len(receiver),stock_wrapper_value=raw_value))
report=dict(passed=True,original_dispatch_and_filter=True,stock_receiver_modeled=False,native_player_play_state=False,physical_device_accessed=False,cases=cases,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_gui.h','runtime/platform/player/stock_image.h','tools/test_stock_gui_host.py']},limits=['Loaded-image identity and the negative filtered case are modeled; final receiver instructions execute.','Skip tests model UI entry/exit, logging, track-selector validation, allocator and mutex/ticket/wakeup primitives. Original stable-state handlers, controller request construction and queue admission execute.','The active component flag is not PLAYING/PAUSED.','The binding requires an installed in-process owner-thread service; it is not an independent client endpoint.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
