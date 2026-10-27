"""Original manager change prefix -> registered native notification callback; offline only."""
from pathlib import Path
import argparse,hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ack-registered',action='store_true',help='Complete change state, then native inactive ack; target already registered, transport/lookup virtual.')
parser.add_argument('--wrong-app-ack',action='store_true',help='Supply target app inactive ack instead of current app; require no activation/transition.')
parser.add_argument('--fresh-target',action='store_true',help='Native first-launch parent path with virtual fork/registry, then inject target state1; implies ack mode.')
parser.add_argument('--register-target',action='store_true',help='Use original registration handler instead of direct target state1 update; requires fresh target.')
parser.add_argument('--proxy-register',action='store_true',help='Generate registration with original proxy and feed original reply back; implies fresh/register modes.')
parser.add_argument('--activate-proxy',action='store_true',help='Native manager event framing -> proxy receive loop -> activation ack -> virtual frontend fork.')
parser.add_argument('--capture-frontend-exec',action='store_true',help='Take virtual proxy fork child branch and stop at execvp; never execute frontend.')
parser.add_argument('--no-launch-arguments',action='store_true',help='Capture original proxy exec with an AppList entry containing zero optional arguments.')
parser.add_argument('--walkman-request',action='store_true',help='Captured Responder op6 -> native current-Responder notification prefix; stop before state transition.')
parser.add_argument('--inactive-confirmation-report',help='Consume actual Home cleanup APF state1 packet through original manager f75c; transport remains virtual.')
parser.add_argument('--home-switch-report',help='Consume native Home switch wire request and subsequent same-client inactive confirmation.')
parser.add_argument('--native-launch-config',action='store_true',help='Reuse native parser/query manager memory and execute original launch-entry lookup; requires Home lookup report.')
parser.add_argument('--native-process-registry',action='store_true',help='Execute original process list construction/find/count/insertion during first launch; OS effects still virtual.')
parser.add_argument('--save-manager-state',action='store_true',help='Save local model RAM after first native registry activation, never device memory.')
parser.add_argument('--native-ipc-service',action='store_true',help='Construct original IPC service/pool/observer at start; separate offline variant.')
args=parser.parse_args()
if args.native_ipc_service:args.native_process_registry=True;args.save_manager_state=True
if args.save_manager_state:assert args.native_process_registry
if args.native_process_registry:args.native_launch_config=True
if args.native_launch_config:
 assert args.home_switch_report and not args.no_launch_arguments
 args.capture_frontend_exec=True
home_switch_input=None;home_switch_packet=None;home_switch_replies=[];home_lookup_used=False;combined_home_actor=False;root_activation_route=False
if args.home_switch_report:
 assert not args.walkman_request and not args.wrong_app_ack
 if args.inactive_confirmation_report:assert args.inactive_confirmation_report==args.home_switch_report
 args.inactive_confirmation_report=args.home_switch_report
 path=(ROOT/args.home_switch_report).resolve();assert path.is_relative_to(ROOT/'sources')
 content=path.read_bytes();home=json.loads(content)
 root_activation_route=bool(home.get('native_activation_route'))
 combined_home_actor=bool(home.get('native_frame_receiver')) and any(row['rebuild_cycle']==1 for row in home['cases'])
 entry_cases=[row for row in home['cases'] if row['rebuild_cycle']==0]
 requests=[row['native_switch_wire_requests'][0] for row in entry_cases]
 assert len(requests)==2 and requests[0]==requests[1]
 home_switch_packet=bytes.fromhex(requests[0]['packet_hex']);assert len(home_switch_packet)==1060 and hashlib.sha256(home_switch_packet).hexdigest()==requests[0]['packet_sha256']
 lookup_requests=[row.get('native_lookup_wire_requests',[]) for row in entry_cases]
 if any(lookup_requests):
  assert len(lookup_requests[0])==1 and lookup_requests[0]==lookup_requests[1]
  assert lookup_requests[0][0]['words']==[276,0,1,36,55]
  assert list(struct.unpack('<5I',bytes.fromhex(lookup_requests[0][0]['reply_hex'])))==[20,0,36,0,0x30001]
  home_lookup_used=True
 assert requests[0]['words']==[1060,1 if home_lookup_used else 0,1,6,55,0x30001,0,0]
 home_switch_input={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(content).hexdigest(),'packet_hex':home_switch_packet.hex(),'words':requests[0]['words'],'native_name_lookup_used':home_lookup_used,'combined_home_actor':combined_home_actor,'native_activation_route':root_activation_route}
inactive_input=None;inactive_packet=None;inactive_replies=[]
if args.inactive_confirmation_report:
 assert not any((args.walkman_request,args.wrong_app_ack))
 args.ack_registered=True
 path=(ROOT/args.inactive_confirmation_report).resolve();assert path.is_relative_to(ROOT/'sources')
 content=path.read_bytes();home=json.loads(content)
 candidate=(ROOT/'work/home-entry-candidate/SpiderApp.analysis-only.elf').read_bytes()
 assert home['candidate_sha256']==hashlib.sha256(candidate).hexdigest()
 packets=[]
 for row in home['cases']:
  if combined_home_actor and row['rebuild_cycle']!=0:continue
  close=row['native_manager_close'];assert close['via_command6_consumer'] and close['client_state_after']==1
  trace=close['trace'];assert next(i for i,item in enumerate(trace) if item.get('call')=='close')<next(i for i,item in enumerate(trace) if 'apf_ack' in item)
  packets.extend(close['apf_ack_requests'])
 assert len(packets)>=2 and all(packet==packets[0] for packet in packets)
 inactive_packet=packets[0];assert inactive_packet==[24,3 if root_activation_route else 2 if home_lookup_used else 1 if home_switch_input else 0,1,1,55,1]
 inactive_input={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(content).hexdigest(),'packet':inactive_packet,'candidate_sha256':home['candidate_sha256']}
walkman_input=None
if args.walkman_request:
 assert not any((args.ack_registered,args.wrong_app_ack,args.fresh_target,args.register_target,args.proxy_register,args.activate_proxy,args.capture_frontend_exec,args.no_launch_arguments))
 source_path='sources/native-responder-walkman-lookup-reply.json'
 source_bytes=(ROOT/source_path).read_bytes();source=json.loads(source_bytes)
 assert source['all_passed'] and source['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
 captured=next(r for r in source['cases'] if r['case']=='success')['requests'][1]
 packet=bytes.fromhex(captured['packet_hex']);assert len(packet)==1060 and hashlib.sha256(packet).hexdigest()==captured['packet_sha256']
 assert captured['words']==[1060,56,2,6,66,1,1,0]
 walkman_input={'path':source_path,'sha256':hashlib.sha256(source_bytes).hexdigest(),'packet':packet.hex()}
if args.no_launch_arguments:args.capture_frontend_exec=True
if args.capture_frontend_exec:args.activate_proxy=True
if args.activate_proxy:args.proxy_register=True
if args.proxy_register:args.fresh_target=True;args.register_target=True
if args.fresh_target:args.ack_registered=True
assert not (args.fresh_target and args.wrong_app_ack)
assert not args.register_target or args.fresh_target
assert not args.wrong_app_ack or args.ack_registered
raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf=ELFFile(io.BytesIO(raw));rows=[]
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
if args.proxy_register:
 proxy_raw=(ROOT/'work/targets-jp/appproxy').read_bytes()
 assert hashlib.sha256(proxy_raw).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
 proxy_elf=ELFFile(io.BytesIO(proxy_raw))
 proxy_symbols={s.name:s['st_value'] for s in proxy_elf.get_section_by_name('.dynsym').iter_symbols()}
for target in ((0x30001,) if home_switch_input else (1,) if args.walkman_request else (0x30001,0x30002)):
 current=2 if args.walkman_request else 1
 native_config_details=None;native_entry_returns=[];native_entry_spies=[];registry_events=[]
 if args.native_launch_config:
  from native_lookup_fixture import lookup
  assert home_lookup_used
  version=(ROOT/'VERSION').read_text().strip();config_path=ROOT/'work'/('integration-'+version)/'system-overlay/etc/AppList.conf';config=config_path.read_bytes()
  captured_lookup=home['cases'][0]['native_lookup_wire_requests'][0]
  assert hashlib.sha256(config).hexdigest()==captured_lookup['parser']['config_sha256']
  session={};native_config_details={};reply,_=lookup(ROOT,bytes.fromhex(captured_lookup['packet_hex']),config_bytes=config,details=native_config_details,session=session)
  assert reply.hex()==captured_lookup['reply_hex'];u=session['emulator'];assert session['core']==0x60000000
  native_config_details.update({'config_path':str(config_path.relative_to(ROOT)),'entry_lookup':native_entry_spies})
 else:
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
  for s in elf.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 core=0x60000000;changer=core+0x4b88;notifications=[];lookups=[];state_notices=[];phase='init';process_exists=not args.fresh_target;forks=[];commands=[];registration_replies=[];registration_timeline=[];event_queue=[];event_frames=[];activation_replies=[]
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 def cstr(p):return bytes(u.mem_read(p,1024)).split(b'\0')[0].decode()
 if args.fresh_target and not args.native_launch_config:
  put(0x60012000,target)
  u.mem_write(0x60012004,b'/contents/HOMEBREW/launcher/app\0')
  put(0x60012104,0 if args.no_launch_arguments else 1);u.mem_write(0x60012108,b'--native\0')
 def hook(uc,pc,size,data):
  global process_exists
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  result=0
  if args.native_ipc_service and pc==0xf314:
   message=list(struct.unpack('<3I',uc.mem_read(a[0],12)))
   notifications.append({'recipient':a[1],'packet':message})
   if phase=='registration' and message[0]==5:registration_timeline.append('target-activation5')
   return
  if args.native_ipc_service and pc==0xf298:
   state_notices.append(list(struct.unpack('<3I',uc.mem_read(a[0],12))));return
  if args.native_ipc_service and pc in (0x16cb0,0x19410):
   put(a[0] if pc==0x16cb0 else a[2],44 if pc==0x16cb0 else 77)
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_process_registry and pc in (0x162b4,0x1633c,0x16510,0x16578,0x16594,0x165fc,0x110ac):registry_events.append({'procedure':hex(pc),'phase':phase})
  if args.native_launch_config and pc in native_entry_returns:
   table=word(core+4);records=word(core);expected=next(table+i*0x510 for i in range(records) if word(table+i*0x510)==target)
   assert a[0]==expected;native_entry_spies.append({'returned_record':hex(a[0]),'name':cstr(a[0]+4)});return
  if args.fresh_target and pc==0x11184:
   vector=a[0];tokens=[]
   for i in range(8):
    pointer=word(vector+i*4)
    if not pointer:break
    tokens.append(cstr(pointer))
   assert tokens==['appproxy','/contents/HOMEBREW/launcher/app']+([] if args.no_launch_arguments else ['--native'])
   commands.append(tokens);return
  if phase=='change' and pc==0x1485c and not args.ack_registered:uc.emu_stop();return
  if pc in (0x1a458,0x1a4f0,0x1a508):pass
  elif pc==0x11538:
   assert a[:2]==[core,target];result=1
  elif pc==0x110ac:
   if args.native_process_registry:
    lookups.append(a[:2]);return
   assert a[0]==core and a[1] in (current,target);lookups.append(a[:2]);result=0x60010000 if a[1]==current else 0x60010100 if process_exists else 0
  elif args.walkman_request and pc==0x16510:
   assert word(a[2])==current;result=0x60010000
  elif args.walkman_request and pc==0x16578:pass
  elif args.fresh_target and pc==0x15b28:
   if args.native_launch_config:
    assert a[:2]==[core,target];native_entry_returns.append(uc.reg_read(UC_ARM_REG_LR));return
   assert a[1]==target;result=0x60012000
  elif args.fresh_target and pc==0x16594:
   if args.native_process_registry:return
   result=1
  elif args.fresh_target and pc==symbols['fork']:
   forks.append(321);result=321
  elif args.fresh_target and pc==0x1b858:
   if args.native_ipc_service and a[0]==0x6000601c:return
   result=0x60014000 if args.register_target and a[0]==0x6000601c else 0x60010100
  elif args.fresh_target and pc==0x1633c:
   if a[0]==core+8:
    if args.native_process_registry and phase=='init':
     assert a[1]==0x60010000 and word(a[1]+8)==current
     return
    assert a[1]==0x60010100 and word(a[1]+4)==321 and word(a[1]+8)==target and word(a[1]+12)==0
    if args.native_process_registry:return
    process_exists=True
   else:
    assert args.register_target and a[0]==0x60006008
    return  # Original event-port linked-list insertion executes.
  elif args.fresh_target and pc==symbols['strlen']:result=len(cstr(a[0]))
  elif args.fresh_target and pc==symbols['memcpy']:
   uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
  elif args.fresh_target and pc==0x1b3c8:
   data_bytes=cstr(a[2]).encode()+b'\0';assert len(data_bytes)<=a[1];uc.mem_write(a[0],data_bytes)
  elif args.ack_registered and pc==0x16510:
   if args.native_process_registry:return
   app=word(a[2]);assert app in (1,target,321)
   result=0x60010000 if app==1 else 0x60010100
  elif home_switch_input and phase=='change' and pc==0x16d18:
   assert a[:2]==[44,55] and a[3]==16
   reply=list(struct.unpack('<4I',uc.mem_read(a[2],16)));assert reply==[16,home_switch_input['words'][1],6,0];home_switch_replies.append(reply)
  elif args.register_target and pc==0x16d18 and not (args.inactive_confirmation_report and phase=='ack'):
   assert a[0]==44
   if args.activate_proxy and a[1]==643:
    assert a[3]==20
    frame=bytes(uc.mem_read(a[2],20))
    if args.native_ipc_service:assert list(struct.unpack('<5I',frame))[:2]==[20,0]
    else:assert list(struct.unpack('<5I',frame))==[20,0,5,0,0]
    event_frames.append(frame)
   elif args.activate_proxy and a[3]==16:
    assert a[1]==642
    reply=bytes(uc.mem_read(a[2],16));assert list(struct.unpack('<4I',reply))[2:]==[1,0]
    activation_replies.append(reply)
   else:
    assert a[1]==642 and a[3]==20
    reply=list(struct.unpack('<5I',uc.mem_read(a[2],20)))
    assert reply==[20,0,0,0,target]
    registration_replies.append(reply);registration_timeline.append('registration-reply')
  elif args.activate_proxy and pc==0x1967c:
   assert a[2:]==[52,0];event_queue.append(bytes(uc.mem_read(a[1],52)))
  elif args.activate_proxy and pc==0x1978c:
   if not event_queue:uc.emu_stop();return
   uc.mem_write(a[1],event_queue.pop(0))
  elif args.ack_registered and pc==0x16578:
   if args.native_process_registry:return
  elif args.ack_registered and pc==0x11650:
   assert a[:3]==[core,target,0]  # Target argv update is outside this check.
  elif args.ack_registered and pc==0x50000300:
   packet=list(struct.unpack('<3I',uc.mem_read(a[0],12)))
   assert packet in ([9,1,target if args.wrong_app_ack else 1],[9,0,target],[9,1,target],[9,2,target]) and a[1]==0x60011000
   state_notices.append(packet)
  elif args.inactive_confirmation_report and phase=='ack' and pc==0x16d18:
   assert a[:2]==[44,inactive_packet[4]] and a[3]==16
   reply=list(struct.unpack('<4I',uc.mem_read(a[2],16)));assert reply==[16,inactive_packet[1],inactive_packet[3],0]
   inactive_replies.append(reply)
  elif args.ack_registered and pc in (0xa188,0x1c4d0,0xa30c):pass
  elif pc==0x50000100:
   packet=list(struct.unpack('<3I',uc.mem_read(a[0],12)))
   assert (packet,a[1]) in (([6,0,0],current),([4,0,0],current),([5,0,0],target)) and a[2]==0x60011000
   notifications.append({'recipient':a[1],'packet':packet})
   if phase=='registration' and packet[0]==5:registration_timeline.append('target-activation5')
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 def call(pc,values,end=0x50000000):
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(pc,end,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==(0x1978c if pc==0xf0fc and args.activate_proxy else end)
  return u.reg_read(UC_ARM_REG_R0)
 if args.native_process_registry:
  assert call(0x162b4,(core+8,))==0
  call(0x165fc,(0x60010000,432,current));assert call(0x1633c,(core+8,0x60010000))==0
  assert call(0x110ac,(core,current))==1 and call(0x110ac,(core,target))==0 and call(0x16594,(core+8,0,0))==1
  lookups.clear()
 assert call(0x14648,(changer,core,0x211dc))==0
 assert word(changer+0x4a0)==0xbd74
 active_state=call(0x14c84,())
 assert word(active_state+0x10)==0x14e14
 put(changer,active_state)  # Active changer state is a supplied runtime precondition.
 put(changer+4,current);put(core+0x503c,1 if args.walkman_request else 2)
 if args.walkman_request:put(0x6001000c,2) # supplied active Responder registry record
 if args.native_ipc_service:
  call(0xefd4,(0x60006000,core))
  assert word(core+0x51b4)==0xf298 and word(core+0x51bc)==0xf314
 else:put(core+0x51bc,0x50000100);put(core+0x51c0,0x60011000)
 phase='change'
 if args.walkman_request:
  ipc,request=0x60015000,0x60016000
  put(ipc,core);put(ipc+4,44);u.mem_write(request,bytes.fromhex(walkman_input['packet']))
  call(0xfa44,(ipc,request),0x1485c)
 elif home_switch_input:
  ipc,request=0x60015000,0x60016000;put(ipc,core);put(ipc+4,44);u.mem_write(request,home_switch_packet)
  call(0xfa44,(ipc,request));assert home_switch_replies==[[16,home_switch_input['words'][1],6,0]]
 else:call(0xcddc,(core,target,0,0),0x50000000 if args.ack_registered else 0x1485c)
 assert notifications==[{'recipient':current,'packet':[4 if args.walkman_request else 6,0,0]}] and lookups==[[core,current]],(notifications,lookups)
 assert word(changer+8)==target
 state_after_change=word(changer);ack_result=None;proxy_registration=None
 if args.ack_registered:
  assert state_after_change==call(0x14d10,())
  call(0x10f4c,(core,0xb614,core))
  assert word(core+0x41b8)==0xb614 and word(core+0x41bc)==core
  put(core+0x5144,1);put(core+0x5148,99)
  if not args.native_ipc_service:put(core+0x51b4,0x50000300);put(core+0x51b8,0x60011000)
  put(0x6001000c,2)
  phase='ack'
  ack_app=target if args.wrong_app_ack else 1
  if args.inactive_confirmation_report:
   ipc,request=0x60015000,0x60016000;put(ipc,core);put(ipc+4,44);u.mem_write(request,struct.pack('<6I',*inactive_packet))
   ack_result=call(0xf75c,(ipc,request));assert inactive_replies[-1]==[16,inactive_packet[1],1,0]
  else:ack_result=call(0xc86c,(core,ack_app,1))
  assert ack_result==0 and word(0x6001010c if args.wrong_app_ack else 0x6001000c)==1
  if args.native_process_registry:process_exists=call(0x110ac,(core,target))==1
  assert state_notices[:1]==[[9,1,ack_app]]
  if not args.fresh_target:assert state_notices==[[9,1,ack_app]]
  if args.wrong_app_ack:
   assert notifications==[{'recipient':1,'packet':[6,0,0]}]
   assert word(changer)==state_after_change and word(changer+4)==1 and word(0x6001000c)==2
  elif args.fresh_target:
   assert forks==[321] and len(commands)==1 and process_exists
   assert word(0x6001010c)==0 and word(changer)==call(0x14eac,())
   assert notifications==[{'recipient':1,'packet':[6,0,0]}] and state_notices==[[9,1,1],[9,0,target]]
   if args.register_target:
    ipc=0x60006000
    put(ipc,core);put(ipc+4,44)
    if not args.native_ipc_service:
     assert call(0x162b4,(ipc+8,))==0
     put(ipc+8,0x167ec)
    else:assert word(ipc+24)==0 and word(ipc+28+12)==0
    phase='registration'
    if args.proxy_register:
     p=Uc(UC_ARCH_ARM,UC_MODE_ARM);p.mem_map(0x8000,0x40000)
     for segment in proxy_elf.iter_segments():
      if segment['p_type']=='PT_LOAD':p.mem_write(segment['p_vaddr'],segment.data())
     p.mem_map(0x50000000,4096);p.mem_map(0x60000000,0x30000)
     proxy_context=0x1ca5c;proxy_requests=[];opened_ports=[];threads=[];proxy_trace=[];proxy_mode='registration';event_received=False;event_delivery_index=0;frontend_forks=[];frontend_exec=[];proxy_recent=[]
     def pword(address):return struct.unpack('<I',p.mem_read(address,4))[0]
     def pput(address,value):p.mem_write(address,struct.pack('<I',value))
     def proxy_hook(uc,pc,size,data):
      global event_received,event_delivery_index
      pa=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
      if args.native_ipc_service:
       proxy_recent.append({'pc':hex(pc),'r0':hex(pa[0]),'r1':hex(pa[1]),'r2':hex(pa[2])})
       if len(proxy_recent)>24:proxy_recent.pop(0)
      result=0
      if args.native_ipc_service and pc==0xe960:pput(pa[0],0x6002a000)
      elif pc==proxy_symbols['getpid']:result=321
      elif pc==0xd258:
       opened_ports.append(pa[1]);pput(pa[0],500+len(opened_ports)-1)
      elif pc==0xd2c0:
       assert pa[:2]==[500,55]
       if proxy_mode=='activation':
        assert pa[3]==24
        packet=bytes(uc.mem_read(pa[2],24));request=list(struct.unpack('<6I',packet))
        assert request[0]==24 and request[2:]==[target,1,642,2]
        proxy_requests.append(request);proxy_trace.append('activation-state2-request')
        u.mem_write(0x60015000,packet);call(0xf75c,(ipc,0x60015000))
       else:
        assert pa[3]==32
        packet=bytes(uc.mem_read(pa[2],32));request=list(struct.unpack('<8I',packet))
        assert request==[32,0,0,0,642,643,321,0x10010001]
        proxy_requests.append(request);proxy_trace.append('registration-request')
        u.mem_write(0x60015000,packet);call(0xf584,(ipc,0x60015000))
      elif pc==0xd36c:
       if proxy_mode=='activation' and pa[0]==501:
        assert pa[2]==256
        if args.native_ipc_service:
         if event_delivery_index>=len(event_frames):uc.emu_stop();return
         frame=event_frames[event_delivery_index];event_delivery_index+=1
        else:
         if event_received:uc.emu_stop();return
         assert len(event_frames)==1;frame=event_frames[0]
        uc.mem_write(pa[1],frame);pput(pa[3],20);event_received=True;proxy_trace.append('native-event-'+str(struct.unpack('<5I',frame)[2])+'-received')
       elif proxy_mode=='activation':
        assert pa[0]==500 and pa[2]==16 and len(activation_replies)==1
        uc.mem_write(pa[1],activation_replies[0]);pput(pa[3],16);proxy_trace.append('activation-state2-reply-read')
       else:
        assert pa[0]==500 and pa[2]==20 and len(registration_replies)==1
        uc.mem_write(pa[1],struct.pack('<5I',*registration_replies[0]));pput(pa[3],20)
        proxy_trace.append('registration-reply-read')
      elif args.activate_proxy and pc==proxy_symbols['fork']:
       assert pword(proxy_context+4)==2 and word(0x6001010c)==2
       result=0 if args.capture_frontend_exec else 432
       frontend_forks.append(result);proxy_trace.append('frontend-fork-request')
      elif args.capture_frontend_exec and pc==proxy_symbols['execvp']:
       executable=bytes(uc.mem_read(pa[0],256)).split(b'\0')[0].decode();child_argv=[]
       for i in range(8):
        pointer=pword(pa[1]+4*i)
        if not pointer:break
        child_argv.append(bytes(uc.mem_read(pointer,256)).split(b'\0')[0].decode())
       assert executable=='/contents/HOMEBREW/launcher/app' and child_argv==[executable]+([] if args.no_launch_arguments else ['--native'])
       frontend_exec.append({'path':executable,'argv':child_argv});proxy_trace.append('execvp-captured-not-executed')
       uc.emu_stop();return
      elif pc==0xe534:
       assert pa[:2]==[0x9b40,proxy_context]
       pput(pword(uc.reg_read(UC_ARM_REG_SP)),1234);threads.append(pa[0]);proxy_trace.append('receiver-thread-request')
      elif pc in (0xfbf8,0xfc38):raise AssertionError('Unexpected proxy panic')
      elif pc not in (0xea80,0xeae8,0x98bc,0xf840):return
      uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
     p.hook_add(UC_HOOK_CODE,proxy_hook);p.hook_add(UC_HOOK_INTR,intr)
     if args.activate_proxy:
      pput(0x1ca40,proxy_context)
      if args.native_ipc_service:
       for register,value in ((UC_ARM_REG_R0,proxy_context),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):p.reg_write(register,value)
       p.emu_start(0x9904,0x50000000,count=10000);assert p.reg_read(UC_ARM_REG_PC)==0x50000000
       assert pword(proxy_context+0x2c+9*4)==0x9da0
      for event,callback in ((4,0x95c0),(5,0x95c4),(6,0x969c)):
       for register,value in ((UC_ARM_REG_R0,proxy_context),(UC_ARM_REG_R1,event),(UC_ARM_REG_R2,callback),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):p.reg_write(register,value)
       p.emu_start(0x9d64,0x50000000,count=10000)
       assert p.reg_read(UC_ARM_REG_PC)==0x50000000 and pword(proxy_context+0x2c+event*4)==callback
     for register,value in ((UC_ARM_REG_R0,proxy_context),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):p.reg_write(register,value)
     p.emu_start(0xcdec,0x50000000,count=200000)
     assert p.reg_read(UC_ARM_REG_PC)==0x50000000 and p.reg_read(UC_ARM_REG_R0)==0
     assert pword(proxy_context)==target and pword(proxy_context+4)==1 and pword(proxy_context+0x24)==1
     assert threads==[0x9b40] and opened_ports==[642,643]
     proxy_registration={'requests':proxy_requests,'client_state':pword(proxy_context+4),'receiver_thread_requests':[hex(x) for x in threads],'trace':proxy_trace}
    else:
     u.mem_write(0x60015000,struct.pack('<8I',32,0,0,0,642,643,321,0x10010001))
     call(0xf584,(ipc,0x60015000))
    assert registration_replies==[[20,0,0,0,target]]
    port_node=word(ipc+24)
    if args.native_ipc_service:assert ipc+48<=port_node<ipc+432 and word(ipc+28+12)==1
    else:assert port_node==0x60014000
    assert [word(port_node+offset) for offset in (4,8)]==[target,643]
    assert registration_timeline==['target-activation5','registration-reply']
   else:
    assert call(0xc86c,(core,target,1))==0  # State update injected; not a full registration request.
   assert state_notices[-1]==[9,1,target] and word(0x6001010c)==1
   assert notifications[-1]=={'recipient':target,'packet':[5,0,0]}
   assert word(changer)==call(0x15050,())
   if args.activate_proxy:
    put(ipc+0x1b0,77)
    if not args.native_ipc_service:
     u.mem_write(0x60016000,struct.pack('<3I',*notifications[-1]['packet']))
     call(0xf314,(0x60016000,target,ipc))
    call(0xf0fc,(ipc,))
    assert sum(struct.unpack('<5I',frame)[2]==5 for frame in event_frames)==1
    if args.capture_frontend_exec:
     # Model OS argv from the actual native manager command, then execute main's staging instructions.
     vector=0x60020000;cursor=0x60021000
     for i,token in enumerate(commands[0]):
      pput(vector+i*4,cursor);encoded=token.encode()+b'\0';p.mem_write(cursor,encoded);cursor+=len(encoded)
     pput(vector+len(commands[0])*4,0)
     p.reg_write(UC_ARM_REG_R6,vector);p.reg_write(UC_ARM_REG_R4,0x1ca44)
     p.emu_start(0x9778,0x9790,count=32)
     assert p.reg_read(UC_ARM_REG_PC)==0x9790 and pword(0x1ca50)==vector+4 and pword(0x1ca4c)==pword(vector+4)
    phase='proxy-activation';proxy_mode='activation'
    for register,value in ((UC_ARM_REG_R0,proxy_context),(UC_ARM_REG_SP,0x60028000),(UC_ARM_REG_LR,0x50000000)):p.reg_write(register,value)
    try:p.emu_start(0x9b40,0x50000000,count=200000)
    except Exception:
     if args.native_ipc_service:(ROOT/'work/native-ipc-proxy-model-gap.json').write_text(json.dumps({'recent':proxy_recent,'frames':[list(struct.unpack('<5I',frame)) for frame in event_frames],'trace':proxy_trace},indent=2)+'\n')
     raise
    assert p.reg_read(UC_ARM_REG_PC)==(proxy_symbols['execvp'] if args.capture_frontend_exec else 0xd36c) and event_received
    assert pword(proxy_context+4)==2 and word(0x6001010c)==2 and frontend_forks==([0] if args.capture_frontend_exec else [432])
    if args.capture_frontend_exec:assert len(frontend_exec)==1
    else:assert pword(0x1c834)==432
    assert word(changer)==active_state
    activation_frame=next(frame for frame in event_frames if struct.unpack('<5I',frame)[2]==5)
    proxy_registration['activation']={'native_event_frame':list(struct.unpack('<5I',activation_frame)),'native_event_frames':[list(struct.unpack('<5I',frame)) for frame in event_frames],'proxy_requests':proxy_requests[1:],'client_state_after':pword(proxy_context+4),'manager_record_state_after':word(0x6001010c),'virtual_frontend_fork_results':frontend_forks,'captured_frontend_exec_requests':frontend_exec,'trace':proxy_trace.copy()}
    proxy_registration['native_ports']={'reply_address':pword(proxy_context+12),'reply_handle':pword(proxy_context+16),'event_address':pword(proxy_context+24),'event_handle':pword(proxy_context+28)}
  else:
   assert notifications==[{'recipient':1,'packet':[6,0,0]},{'recipient':target,'packet':[5,0,0]}]
   assert word(changer)==call(0x15050,()) and word(changer+4)==0
 rows.append({'target':hex(target),'current_app_fixture':1,'native_callback_table':'0x211dc','native_callback_at_4a0':hex(word(changer+0x4a0)),'native_change_method':hex(word(active_state+0x10)),'notifications':notifications,'stored_target':hex(word(changer+8)),'state_after_change':hex(state_after_change),'state_after_ack':hex(word(changer)) if args.ack_registered else None,'ack_return':ack_result,'state_observer_packets':state_notices,'virtual_fork_parent_pids':forks,'native_exec_commands':commands,'registration_replies':registration_replies,'registration_timeline':registration_timeline,'proxy_registration':proxy_registration})
report={'sysmgrd_sha256':digest,'cases':rows,'chain':['0xcddc','0x1480c','0x14b94','0x14e14','0x149e0','0xbd74','0xa62c','registered observer packet6'],'limits':['Original changer constructor and callback table execute; active changer state/current app/core state are supplied runtime preconditions.','Locks, application-existence checks and notification transport are virtual. Stops before1485c state transition, with outer change lock still held.','No actual IPC delivery, acknowledgement, launch, complete state transition or hardware switch qualification.']}
if args.ack_registered:
 report['limits'][1]='Locks, application-existence/registry search and notification transport are virtual; original changer state transitions execute.'
 report['limits'][2]='No actual IPC delivery, process creation, target activation acknowledgement or hardware switch qualification.'
 report['limits'].append('Original changer transition and c86c/11558 state1 ack -> registered b614 callback -> changer execute; target already exists by fixture. Registry search/unlock, argv update, observer transport and core helpera30c virtual. No process creation, real IPC or target activation acknowledgement.')
if args.fresh_target:
 report['limits']=[line.replace('target already exists by fixture.','Target initially absent in this variant.').replace('No actual IPC delivery, process creation, target activation acknowledgement or hardware switch qualification.','No actual IPC delivery, process execution, target activation acknowledgement or hardware switch qualification.') for line in report['limits']]
 report['limits'].append('Fresh target uses original110e0/10f64/fork-wrapper/165fc/1662c parent path with supplied AppList-shaped entry, virtual fork321, record allocation/insertion and configuration lookup. Target state1 update injected after state0 constructor; no actual registration request, exec or process runs.')
if args.register_target:
 report['limits']=[line.replace('Target state1 update injected after state0 constructor; no actual registration request, exec or process runs.','Target state1 now comes from the original registration handler; request/transport remain fixtures, with no actual exec or process execution.') for line in report['limits']]
 report['limits'].append('Direct target state1 injection replaced by original f584 registration handler/core/event-port constructor and linked-list insertion. Registration request bytes, ports and allocation are fixtures; response transport virtual. Activation5 is requested before registration reply in this native path; no real concurrent delivery or proxy receive loop.')
if args.proxy_register:
 report['limits']=[line.replace('Registration request bytes, ports and allocation are fixtures; response transport virtual.','Registration request bytes come from original proxy; ports/allocation/response transport are virtual.').replace('request/transport remain fixtures','request is generated natively and transport remains virtual') for line in report['limits']]
 report['limits'].append('Original proxy cdec generates actual request bytes; manager f584 reply feeds back into native proxy registration/state update. Ports/transport/getpid/thread creation virtual; receiver thread entry requested but not run and activation5 not yet delivered to proxy.')
 report['appproxy_sha256']=hashlib.sha256(proxy_raw).hexdigest()
if args.activate_proxy:
 report['limits']=[line.replace('receiver thread entry requested but not run and activation5 not yet delivered to proxy.','receiver thread entry executes cooperatively in this mode; OS thread creation remains virtual.').replace('no real concurrent delivery or proxy receive loop.','no real concurrent delivery; proxy receive-loop instructions execute in the cooperative activation mode.') for line in report['limits']]
 report['limits'].append('Original manager f314/f0fc event framing/recipient traversal feed original proxy9b40 after native9d64 callback registration. Original activation ack feeds managerf75c and reply feeds proxy, then fork returns virtual432. Queue/transport/locks/fork/thread scheduling virtual; receiver stops waiting next event, no child/exec/frontend or hardware runs.')
if args.capture_frontend_exec:
 report['limits']=[line.replace('then fork returns virtual432.','then fork returns virtual0 for the child capture branch.').replace('receiver stops waiting next event, no child/exec/frontend or hardware runs.','execution stops at execvp capture; no real child/exec/frontend or hardware runs.') for line in report['limits']]
 report['limits'].append('Virtual fork child branch executes to execvp using manager-produced command copied as OS argv, then original main9778..9790 staging. execvp is captured/stopped, never called; no frontend/device execution. Parent positive-fork branch is a separate mode.')
if walkman_input:
 report['walkman_client_input']=walkman_input
 report['chain']=['0xfa44','0xcddc','0x1480c','0x14b94','0x14e14','0x14984','0xbd44','0xa4d8','registered observer packet4']
 report['limits'].append('Captured Responder op6 parsed by originalfa44, current app2/core state1/active registry record supplied; lookup/record acquisition virtual. Original mode1 chooses14984/bd44/a4d8 and notification4 targets Responder before state transition. Full exit/SpiderApp activation not executed.')
if args.native_launch_config:
 assert native_config_details['native_parser_executed'] and native_config_details['record_count']==7 and len(native_entry_spies)==1
 report['native_launch_configuration']=native_config_details
 if args.native_process_registry:
  assert call(0x16594,(core+8,0,0))==2 and call(0x110ac,(core,1))==1 and call(0x110ac,(core,target))==1
  report['native_process_registry']={'record_count_after_activation':2,'home_preserved':True,'target_found':True,'events':registry_events,'initial_home_state_supplied':True}
  report['limits'].append('Original162b4/165fc/1633c/16510/16578/16594/110ac execute for launch registry; locks/allocation/current Home initial state and fork PID321 remain supplied, predicate11538 still virtual. No actual process creation.')
 report['limits']=[line.replace('supplied AppList-shaped entry','AppList entry from original1574c in the same manager instance') for line in report['limits']]
 report['limits'].append('Native1574c/1084c share this manager memory with launch15b28/10f64. Registry/current app, allocation, IPC, fork and scheduling remain virtual; no boot or physical process execution.')
if args.inactive_confirmation_report:
 report['all_bounded_checks_passed']=True
 report['inactive_confirmation_input']=inactive_input
 report['home_switch_input']=home_switch_input
 report['home_switch_replies']=home_switch_replies
 report['inactive_confirmation_replies']=inactive_replies
 report['source_hashes']={inactive_input['path']:inactive_input['sha256'],'tools/check_manager_change_notification.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'tools/check_home_parent.py':hashlib.sha256((ROOT/'tools/check_home_parent.py').read_bytes()).hexdigest()}
 if args.native_launch_config:
  report['source_hashes']['tools/native_lookup_fixture.py']=hashlib.sha256((ROOT/'tools/native_lookup_fixture.py').read_bytes()).hexdigest()
  report['source_hashes'][native_config_details['config_path']]=hashlib.sha256(config).hexdigest()
 report['limits'].append('Home command6 cleanup-produced packet enters original f75c/c86c/11558/b614/changer in a separate emulator. IPC delivery, registry lookup and actual hardware cleanup remain virtual; no complete stock boot.')
if args.native_ipc_service:
 report['native_ipc_service']={'constructor':'0xefd4','observer':hex(word(core+0x51b4)),'observer_context':hex(word(core+0x51b8)),'port_pool_used':word(0x6000601c+12),'port_pool_capacity':word(0x6000601c+8)}
 report['limits'].append('Original IPC service,port pool,observer and notification bindings constructed at start; socket/queue creation and scheduling virtual.')
if args.save_manager_state:
 assert word(changer)==0x34bd0 and word(changer+4)==target and word(0x6001010c)==2 and word(0x6001000c)==1
 state_dir=ROOT/'work/native-manager-states'/version;state_dir.mkdir(parents=True,exist_ok=True);state_label='native-ipc-launch' if args.native_ipc_service else 'activation-route-launch' if root_activation_route else 'home-actor-launch' if combined_home_actor else 'first-launch';state_path=state_dir/(state_label+'.bin');state=bytes(u.mem_read(core,0x20000));state_path.write_bytes(state)
 report['native_manager_state']={'path':str(state_path.relative_to(ROOT)),'sha256':hashlib.sha256(state).hexdigest(),'bytes':len(state),'base':hex(core),'current_app':target,'target_record':'0x60010100','home_record':'0x60010000','pid':321,'scope':'Model RAM only; not read from any device.'}
 report['source_hashes'][str(state_path.relative_to(ROOT))]=hashlib.sha256(state).hexdigest()
 regions=[]
 for index,segment in enumerate(elf.iter_segments()):
  if segment['p_type']=='PT_LOAD' and segment['p_flags']&2:
   address=segment['p_vaddr'];content=bytes(u.mem_read(address,segment['p_memsz']));path=state_dir/(('native-ipc-' if args.native_ipc_service else 'activation-route-' if root_activation_route else 'home-actor-' if combined_home_actor else '')+'module-data-'+str(index)+'.bin');path.write_bytes(content)
   regions.append({'path':str(path.relative_to(ROOT)),'address':hex(address),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
   report['source_hashes'][str(path.relative_to(ROOT))]=hashlib.sha256(content).hexdigest()
 report['native_manager_state']['module_regions']=regions
(ROOT/('sources/native-manager-native-ipc-exec.json' if args.native_ipc_service else 'sources/native-manager-home-activation-exec.json' if root_activation_route and args.native_process_registry else 'sources/native-manager-home-actor-exec.json' if combined_home_actor and args.native_process_registry else 'sources/native-manager-home-registry-exec.json' if args.native_process_registry else 'sources/native-manager-home-config-exec.json' if args.native_launch_config else 'sources/native-manager-home-lookup-exec.json' if home_lookup_used and args.capture_frontend_exec else 'sources/native-manager-home-lookup-ack.json' if home_lookup_used else 'sources/native-manager-home-wire-exec.json' if home_switch_input and args.capture_frontend_exec else 'sources/native-manager-home-wire-ack.json' if home_switch_input else 'sources/native-manager-home-inactive-exec.json' if args.inactive_confirmation_report and args.capture_frontend_exec else 'sources/native-manager-home-inactive-ack.json' if args.inactive_confirmation_report else 'sources/native-manager-responder-walkman-prefix.json' if args.walkman_request else 'sources/native-manager-proxy-noargs-exec.json' if args.no_launch_arguments else 'sources/native-manager-proxy-exec-request.json' if args.capture_frontend_exec else 'sources/native-manager-proxy-activation.json' if args.activate_proxy else 'sources/native-manager-first-proxy-registration.json' if args.proxy_register else 'sources/native-manager-first-registration.json' if args.register_target else 'sources/native-manager-first-launch.json' if args.fresh_target else 'sources/native-manager-change-wrong-ack.json' if args.wrong_app_ack else 'sources/native-manager-change-ack-registered.json' if args.ack_registered else 'sources/native-manager-change-notification.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Captured Responder request -> native manager -> Responder event4 prefix passed' if args.walkman_request else str(len(rows))+' native manager change cases verified' + ('; native child execvp request captured without optional arguments' if args.no_launch_arguments else '; native child execvp request captured with single frontend path and --native' if args.capture_frontend_exec else '; native event frame -> proxy receive/ack -> manager state2 -> virtual frontend fork' if args.activate_proxy else '; native proxy registration bytes -> manager handler -> native proxy reply/state/thread request' if args.proxy_register else '; original registration handler updates target and requests activation5 before success reply' if args.register_target else '; fresh parent-launch path waits for injected target state1 before activation5' if args.fresh_target else '; wrong-app acknowledgement does not advance switch' if args.wrong_app_ack else '; current-app acknowledgement precedes target activation5 (registered target fixture)' if args.ack_registered else '; current-app event6 prefix only'))
