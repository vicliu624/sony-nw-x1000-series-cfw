"""Original H264 command-thread dispatch to state handler/callback, virtual DSP services."""
from pathlib import Path
import hashlib,io,json,struct,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--spider-callback',action='store_true');parser.add_argument('--target-loaded',action='store_true');parser.add_argument('--native-free-buffers',action='store_true');parser.add_argument('--spider-free-loop',action='store_true');parser.add_argument('--upper-entry',action='store_true');parser.add_argument('--upper-finish',action='store_true');parser.add_argument('--free-handle-error',action='store_true');parser.add_argument('--native-core-free',action='store_true');parser.add_argument('--native-core-thread-exit',action='store_true');parser.add_argument('--native-global-deinit',action='store_true');args=parser.parse_args()
assert not args.target_loaded or args.spider_callback
assert not args.native_free_buffers or args.target_loaded
assert not args.spider_free_loop or args.native_free_buffers
assert not args.upper_entry or args.spider_free_loop
assert not args.upper_finish or args.upper_entry
assert not args.free_handle_error or args.upper_finish
assert not args.native_core_free or (args.upper_finish and not args.free_handle_error)
assert not args.native_core_thread_exit or args.native_core_free
assert not args.native_global_deinit or args.native_core_thread_exit
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/omf_mc_h264d.so').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='8dcb6f2c5cd5a107e3f84daa1f8a72ef420abf59c67bc7281b9ab10d2536a8b2'
elf=ELFFile(io.BytesIO(raw));rows=[];base=0x10000000 if args.spider_callback else 0
for ports in (0,2):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(base+low,high-low)
 for s in segs:u.mem_write(base+s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 if args.spider_callback:
  # Resolve local relative/GLOB_DAT entries needed by the original dispatch table.
  for rel in elf.get_section_by_name('.rel.dyn').iter_relocations():
   p=base+rel['r_offset'];kind=rel['r_info_type']
   if kind==23:put(p,(word(p)+base)&0xffffffff)
   elif kind==21:
    symbol=elf.get_section_by_name('.dynsym').get_symbol(rel['r_info_sym'])
    if symbol['st_shndx']!='SHN_UNDEF':put(p,base+symbol['st_value'])
  spider_raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
  assert hashlib.sha256(spider_raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
  spider=ELFFile(io.BytesIO(spider_raw));spider_segs=[s for s in spider.iter_segments() if s['p_type']=='PT_LOAD']
  sl=min(s['p_vaddr'] for s in spider_segs)&~4095;sh=(max(s['p_vaddr']+s['p_memsz'] for s in spider_segs)+4095)&~4095
  u.mem_map(sl,sh-sl)
  for s in spider_segs:u.mem_write(s['p_vaddr'],s.data())
  spider_symbols={s.name:s['st_value'] for s in spider.get_section_by_name('.dynsym').iter_symbols()}
 handle=0x60001000;private=0x60002000
 for p,v in ((handle+4,1),(handle+8,private),(handle+12,0x60008000),(private+12,2 if args.target_loaded else 3),(private+16,0x60007000),
             (private+28,0x60009000),(private+0x3cc,0x60005000),(private+0x3dc,0x60004000),(private+0xf0,ports)):put(p,v)
 # Derive its stop pointer from native component-init PIC literals; init itself
 # is not executed here, and the resulting private field is supplied explicitly.
 u.reg_write(UC_ARM_REG_R0,0)
 # Its PIC base is formed by original init: pc(3d28)+8 + literal3fac.
 got_base=base+0x3d30+word(base+0x3fac)
 stop_entry=(got_base+word(base+0x3ffc))&0xffffffff
 assert stop_entry==base+0x4014;put(private+0xdc,stop_entry)
 if args.spider_callback:
  owner=0x6000a000;event=0x6000c000;appdata=owner+0x7b0
  put(owner+0x7bc,event);put(owner+0x7c8,owner)
  u.reg_write(UC_ARM_REG_R6,owner);u.reg_write(UC_ARM_REG_SP,0x60018000)
  u.emu_start(0x234dd4,spider_symbols['OMX_GetHandle'],count=1000)
  assert u.reg_read(UC_ARM_REG_PC)==spider_symbols['OMX_GetHandle'] and word(owner+0x750)==0x234a68
  assert u.reg_read(UC_ARM_REG_R2)==appdata
  put(handle+12,appdata);put(private+16,word(owner+0x750))
 message=[0,1,0] if args.target_loaded else [1,2,0]
 u.mem_write(0x60003000,struct.pack('<3I',*message));trace=[];events=[];receive_count=0;event_services=[];sleeps=[];paused_free=False;free_phase=False;free_reports=[];free_services=[];headers=[];upper_services=[];command_stage=False;upper_wait_context=None;teardown_services=[];core_services=[];teardown_phase=False;thread_exit_phase=False;thread_exit_calls=[];global_deinit_services=[]
 if args.native_core_free:
  core_raw=(ROOT/'work/targets-jp/libomx_core.so').read_bytes()
  assert hashlib.sha256(core_raw).hexdigest()=='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
  core=ELFFile(io.BytesIO(core_raw));core_base=0x20000000;cs=[s for s in core.iter_segments() if s['p_type']=='PT_LOAD']
  cl=min(s['p_vaddr'] for s in cs)&~4095;ch=max((s['p_vaddr']+s['p_memsz']+4095)&~4095 for s in cs)
  u.mem_map(core_base+cl,ch-cl)
  for s in cs:u.mem_write(core_base+s['p_vaddr'],s.data())
  got=core_base+0x5aa0+word(core_base+0x5b24);put(got+word(core_base+0x5b28),0x60010000);put(0x60010000,1)
  for off,v in ((4,1),(0x10,handle),(0x40,0x60012000)):put(0x60011000+off,v)
  put(handle+0x4c,base+0x28d4)
  if args.native_global_deinit:
   put(got+0x1bc,0x60014000);put(0x60014000,0x63000000)
   put(got+0x1e4,0x60015000);put(0x60015000,0x63001000)
   put(0x60019004,0);put(0x60019010,0)
 if args.target_loaded:
  for port in range(ports):u.mem_write(private+0x106+port*0x164,struct.pack('<H',1))
  if args.native_free_buffers:
   for port in range(ports):
    record=private+0xf4+port*0x164;n=10 if args.spider_free_loop and port==1 else 1
    u.mem_write(record+0x10,struct.pack('<HH',n,n))
    for slot in range(n):
     index=len(headers);header=0x6000d000+index*0x40;buffer=0x61000000+index*0x100
     headers.append(header);u.mem_write(record+0x14+slot*2,struct.pack('<H',1));put(record+0xd4+slot*4,buffer);put(header+8,buffer)
     if args.spider_free_loop:put(owner+(0x1c if port==0 else 0x75c)+slot*8,header)
   if args.spider_free_loop:put(owner+0x74c,handle);put(handle+0x3c,base+0x260c)
 def hook(uc,pc,size,data):
  global receive_count,paused_free,command_stage,teardown_phase
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if thread_exit_phase:
   local_pc=pc-base if base<=pc<base+high else pc
   if local_pc==0x17b4:
    assert a[1]==0x60004000 and word(0x60013000)==0x7fffffff
    put(a[0],0x60013000);thread_exit_calls.append('receive_termination');ret=0
   elif local_pc==0x16ac:
    assert a[0]==0x60013000;thread_exit_calls.append('free_termination_message');ret=0
   elif local_pc==0x1748:
    assert a[0]==0;thread_exit_calls.append('request_thread_exit');uc.emu_stop();return
   else:return
   uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_global_deinit and core_base<=pc<core_base+ch:
   cp=pc-core_base
   if cp==0x21fc:uc.reg_write(UC_ARM_REG_PC,core_base+0x4ddc);return
   service=None
   if cp==0x2460:
    assert a==[0x63000000,0x63001000,0xffffffff,0xfffffffe];service='send_manager_uninit'
   elif cp==0x2454:
    assert a[1:3]==[0x63001000,0xffffffff];put(a[0],0x60019000);service='receive_manager_reply'
   elif cp==0x2328:assert a[0]==0x60019000;service='free_manager_reply'
   elif cp==0x2400:
    assert a[:2]==[0x60014000,0x60014004] and word(0x60010000)==0;service='terminate_manager_thread'
   elif cp==0x2304:assert a[0]==0x63001000;service='destroy_manager_reply_queue'
   elif cp==0x246c:service='destroy_communication_table'
   elif cp==0x222c:service='deinit_dsp_manager'
   elif cp==0x23d0:service='close_os_wrapper'
   if service:
    global_deinit_services.append(service);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_core_free and pc in (core_base+0x2208,core_base+0x22a4):
   if pc==core_base+0x2208:
    assert a[0]==handle;core_services.append('core_lookup');ret=0x60011000
   else:
    assert a[0] in (handle,0x60012000) and word(0x60011004)==0
    core_services.append('core_free_handle' if a[0]==handle else 'core_free_auxiliary');ret=0
   uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.spider_callback:
   if args.upper_finish and ports and pc in (spider_symbols['OMX_FreeHandle'],spider_symbols['OMX_Deinit']):
    name='OMX_FreeHandle' if pc==spider_symbols['OMX_FreeHandle'] else 'OMX_Deinit'
    if name=='OMX_FreeHandle':assert a[0]==handle
    if args.native_core_free and name=='OMX_FreeHandle':
     teardown_phase=True;teardown_services.append({'service':name,'native_core_dispatch':True})
     uc.reg_write(UC_ARM_REG_PC,core_base+0x5a8c);return
    if args.native_global_deinit and name=='OMX_Deinit':
     teardown_services.append({'service':name,'native_core_dispatch':True})
     uc.reg_write(UC_ARM_REG_PC,core_base+0x5860);return
    ret=0x80001001 if args.free_handle_error and name=='OMX_FreeHandle' else 0
    teardown_services.append({'service':name,'virtual_result':hex(ret)})
    uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   if args.native_core_free and pc==0x235258:
    assert a[0]==0 and all(word(0x60011000+off)==0 for off in (4,0x10,0x40));teardown_phase=False
   if args.upper_entry and ports and pc==spider_symbols['usleep']:
    assert a[0]==1000;upper_services.append('usleep');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   if args.upper_entry and ports and pc==0x235114:command_stage=False
   if args.spider_free_loop and free_phase and pc==0x23d718:
    assert a[:2]==[event,0xffffffff];uc.emu_stop();return
   if pc==0x234a68:
    extra=list(struct.unpack('<2I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),8)))
    assert a==[handle,appdata,0,0] and extra==[1 if args.target_loaded else 2,0] and word(private+12)==2
    if args.target_loaded:assert all(struct.unpack('<H',uc.mem_read(private+0x106+p*0x164,2))[0]==0 for p in range(ports))
    events.append({'args':a,'stack_words':extra,'state_at_callback':2});trace.append('event');return
   for name in ('pthread_mutex_lock','pthread_mutex_unlock','pthread_cond_signal'):
    if pc==spider_symbols[name]:
     assert a[0]==(event if name=='pthread_cond_signal' else event+0x30)
     event_services.append(name);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if base<=pc<base+high:pc-=base
  if teardown_phase:
   if pc in (0x15d4,0x1700):
    uc.reg_write(UC_ARM_REG_PC,base+(0x2858 if pc==0x15d4 else 0x26f8));return
   if pc==0x161c:assert a[0]==12;name='allocate_termination';ret=0x60013000
   elif pc==0x170c:
    assert a[:2]==[0x60004000,0x60013000] and word(a[1])==0x7fffffff;name='post_termination';ret=0
   elif pc==0x1820:
    if args.native_core_thread_exit:
     core_services.append('join_after_native_exit_request');uc.emu_stop();return
    name='virtual_join_thread';ret=0
   elif pc==0x17c0:assert a[:2]==[0,0];name='unmap_empty_port';ret=0
   elif pc==0x16e8:name='destroy_queue';ret=0
   elif pc==0x17e4:name='destroy_mutex';ret=0
   elif pc==0x1730:name='destroy_signal';ret=0
   elif pc==0x16ac:
    assert a[0] in (0x60009000,private);name='free_frame_buffer' if a[0]==0x60009000 else 'free_private';ret=0
   else:return
   core_services.append(name);uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.upper_entry and ports:
   if pc==0x2254:command_stage=True
   if command_stage and pc in (0x1634,0x1784,0x161c,0x170c):
    if pc==0x161c:
     assert a[0]==12;ret=0x60003000;upper_services.append('allocate_command')
    elif pc==0x170c:
     assert a[:2]==[0x60004000,0x60003000] and list(struct.unpack('<3I',uc.mem_read(a[1],12)))==[0,1,0]
     ret=0;upper_services.append('post_command')
    else:
     assert a[0]==0x60005000;ret=0;upper_services.append('command_lock' if pc==0x1634 else 'command_unlock')
    uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_free_buffers and pc in (0x16f4,0x16d0):
   uc.reg_write(UC_ARM_REG_PC,base+(0x2074 if pc==0x16f4 else 0x25a8));return
  if free_phase and pc in (0x1634,0x1784,0x16ac):
   if pc==0x16ac:
    assert a[0] in headers;free_services.append('free_header')
   else:
    assert a[0]==0x60005000;free_services.append('lock' if pc==0x1634 else 'unlock')
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.target_loaded and pc==0x1694:
   sleeps.append({'pending_counts_before':[struct.unpack('<H',uc.mem_read(private+0x106+p*0x164,2))[0] for p in range(ports)]})
   if len(sleeps)==3:
    if args.native_free_buffers:
     trace.append('sleep');paused_free=True;uc.emu_stop();return
    for p in range(ports):uc.mem_write(private+0x106+p*0x164,bytes(2))
   trace.append('sleep');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0x17b4:
   receive_count+=1
   if receive_count==2:uc.emu_stop();return
   assert a[1:3]==[0x60004000,0xffffffff];put(a[0],0x60003000);name='receive';ret=0
  elif pc==0x1634:assert a[:2]==[0x60005000,1];name='lock';ret=0
  elif pc==0x1784:assert a[0]==0x60005000;name='unlock';ret=0
  elif pc==0x16a0:
   assert a[0]==handle and a[2:]==[4,1];name='dsp_command';ret=0
  elif pc==0x1778:assert a[:2]==[handle,0];name='video_deinit';ret=0
  elif pc==0x1604:
   assert a[:3]==[0x60009000,0,512];uc.mem_write(a[0],bytes(a[2]));name='memset';ret=a[0]
  elif pc==0x15ec:
   assert a[0]==handle;name='clear_queue';ret=0
  elif pc==0x182c:uc.reg_write(UC_ARM_REG_PC,base+0x2988);return
  elif pc==0x60007000:
   extra=list(struct.unpack('<2I',uc.mem_read(uc.reg_read(UC_ARM_REG_SP),8)))
   assert a==[handle,0x60008000,0,0] and extra==[2,0]
   assert word(private+12)==2
   events.append({'args':a,'stack_words':extra,'state_at_callback':2});name='event';ret=0
  elif pc==0x16ac:assert a[0]==0x60003000;name='free_message';ret=0
  else:return
  trace.append(name);uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 if args.upper_entry and ports:
  put(owner+0x738,1);u.mem_write(owner+0xf48,b'\x01');put(handle+0x14,base+0x2254)
  if args.upper_finish:u.mem_write(owner+0x748,b'\x01\x01')
  free_phase=True
  u.reg_write(UC_ARM_REG_R0,owner);u.reg_write(UC_ARM_REG_SP,0x60016000);u.reg_write(UC_ARM_REG_LR,0x6001d000)
  u.emu_start(0x2350c4,0,count=30000)
  assert u.reg_read(UC_ARM_REG_PC)==0x23d718
  assert upper_services==['usleep','command_lock','allocate_command','post_command','command_unlock']
  assert free_services==['lock','free_header','unlock']*11
  assert word(owner+0x1c)==0 and all(word(owner+0x75c+i*8)==0 for i in range(10))
  for p in range(ports):
   record=private+0xf4+p*0x164;n=1 if p==0 else 10
   assert struct.unpack('<H',u.mem_read(record+0x12,2))[0]==0
   assert bytes(u.mem_read(record+0x14,n*2))==bytes(n*2)
   free_reports.append({'port':p,'native_free_calls':n,'remaining_count':0,'slot_usage_after':0})
  upper_wait_context=u.context_save();free_phase=False
 u.reg_write(UC_ARM_REG_R0,handle);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(base+0x32fc,0,count=10000)
 if paused_free:
  assert u.reg_read(UC_ARM_REG_PC)==base+0x1694
  saved=u.context_save();resume=u.reg_read(UC_ARM_REG_LR);free_phase=True
  if args.spider_free_loop:
   u.reg_write(UC_ARM_REG_R7,owner);u.reg_write(UC_ARM_REG_R5,0);u.reg_write(UC_ARM_REG_SP,0x60016000)
   u.emu_start(0x235140,0,count=20000)
   assert u.reg_read(UC_ARM_REG_PC)==0x23d718
   assert word(owner+0x1c)==0 and all(word(owner+0x75c+slot*8)==0 for slot in range(10))
  else:
   for port in range(ports):
    header=headers[port]
    for reg,value in ((UC_ARM_REG_R0,handle),(UC_ARM_REG_R1,port),(UC_ARM_REG_R2,header),(UC_ARM_REG_SP,0x60016000),(UC_ARM_REG_LR,0x6001e000)):u.reg_write(reg,value)
    u.emu_start(base+0x260c,0x6001e000,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==0x6001e000 and u.reg_read(UC_ARM_REG_R0)==0
  for port in range(ports):
   record=private+0xf4+port*0x164;n=10 if args.spider_free_loop and port==1 else 1
   assert struct.unpack('<H',u.mem_read(record+0x12,2))[0]==0
   assert bytes(u.mem_read(record+0x14,n*2))==bytes(n*2)
   free_reports.append({'port':port,'native_free_calls':n,'remaining_count':0,'slot_usage_after':0})
  assert free_services==['lock','free_header','unlock']*len(headers)
  free_phase=False;u.context_restore(saved);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,resume)
  u.emu_start(resume,0,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==base+0x17b4 and receive_count==2
 expected_trace=['receive']+['sleep']*(3 if ports and not args.upper_entry else 1)+['event','free_message'] if args.target_loaded else ['receive','lock','dsp_command','video_deinit','memset']+['clear_queue']*ports+['unlock','event','free_message']
 assert trace==expected_trace
 assert word(private+12)==(1 if args.target_loaded else 2) and len(events)==1
 receiver_idle_context=u.context_save() if args.native_core_thread_exit and ports else None
 wait_result=None
 if args.spider_callback:
  assert word(event+0x48)==1
  if upper_wait_context is not None:
   u.context_restore(upper_wait_context);wait_end=0x235200
  else:
   u.reg_write(UC_ARM_REG_R0,event);u.reg_write(UC_ARM_REG_R1,0xffffffff)
   u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000);wait_end=0x6001f000
  u.emu_start(0x23d718,wait_end,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==wait_end and u.reg_read(UC_ARM_REG_R0)==1 and word(event+0x48)==0
  wait_result={'native_wait_return':1,'event_count_after':0,'virtual_pthread_services':event_services}
 finish_result=None
 if args.upper_finish and upper_wait_context is not None:
  u.emu_start(0x235200,0x6001d000,count=10000)
  if args.native_core_thread_exit:
   assert u.reg_read(UC_ARM_REG_PC)==base+0x1820 and receiver_idle_context is not None
   core_join_context=u.context_save();core_resume=u.reg_read(UC_ARM_REG_LR)
   u.context_restore(receiver_idle_context);thread_exit_phase=True
   u.emu_start(base+0x17b4,0,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==base+0x1748 and thread_exit_calls==['receive_termination','free_termination_message','request_thread_exit']
   thread_exit_phase=False;u.context_restore(core_join_context);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,core_resume)
   u.emu_start(core_resume,0x6001d000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x6001d000 and u.reg_read(UC_ARM_REG_R0)==0
  assert bytes(u.mem_read(owner+0x748,2))==bytes(2) and bytes(u.mem_read(owner+0xf48,1))==bytes(1)
  assert [s['service'] for s in teardown_services]==['OMX_FreeHandle','OMX_Deinit']
  finish_result={'upper_return':0,'flags_748_749_f48_after':[0,0,0],'virtual_services':teardown_services,
                 'stored_handle_pointer_unchanged':word(owner+0x74c)==handle,'free_handle_failure_injected':args.free_handle_error}
  if args.native_core_free:
   assert core_services==['core_lookup']+['unmap_empty_port']*2+['free_frame_buffer','allocate_termination','post_termination','join_after_native_exit_request' if args.native_core_thread_exit else 'virtual_join_thread','destroy_queue','destroy_mutex','destroy_mutex','destroy_signal','free_private','core_free_handle','core_free_auxiliary']
   finish_result['native_core_component_services']=core_services
   finish_result['native_thread_exit_path']=thread_exit_calls
   if args.native_global_deinit:
    assert global_deinit_services==['send_manager_uninit','receive_manager_reply','free_manager_reply','terminate_manager_thread','destroy_manager_reply_queue','destroy_communication_table','deinit_dsp_manager','close_os_wrapper']
    assert word(0x60010000)==0 and word(0x60015000)==0
    finish_result['native_global_deinit_services']=global_deinit_services
 rows.append({'initial_state_fixture':2 if args.target_loaded else 3,'message_fixture':message,'port_count_fixture':ports,'native_service_order':trace,'event':events[0],'final_state':word(private+12),'spider_wait':wait_result,'sleep_observations':sleeps,'native_free_buffers':free_reports,'upper_entry_services':upper_services,'upper_wait_resumed_to':'0x235200' if upper_wait_context is not None else None,'upper_finish':finish_result})
report={'component_sha256':digest,'entry':'0x32fc command-thread body','cases':rows,
 'finding':'Original state3 table selects handler35d0 for message1. It executes stop implementation4014, clears port queues, unlocks, then emits event0/data1=0/data2=2 and frees message.',
 'limits':['Component/private state/ports supplied; queue receive, DSP command, video deinit, buffer clearing, memory and mutex services virtual. Handler table and callback wrapper execute original instructions.',
           'No actual component thread, DSP stop, V4L2 deinit or physical frame completion. Callback target is a spy, not SpiderApp; receiver is manually started and stops before next message.']}
if args.spider_callback:
 report['limits'][-1]='Component rebased at10000000 with local relocations; stock SpiderApp registration prefix/callback/post/wait execute in same UC. DSP/video/queue/mutex services remain virtual; receiver and post-notification wait manually scheduled. No whole loader, APF, real thread or hardware completion qualification.'
if args.target_loaded:
 report['finding']='Native state2/message0 handler waits for port buffer counts0 before event0/data2=1; callback runs while private state still2, receiver writes state1 after handler return.'
 report['limits'].append('Port pending counters1 are fixtures, changed to0 by third virtual sleep; no actual FreeBuffer or real resource release. Event callback must not be equated with prior private-state write; final thread bookkeeping occurs afterward.')
if args.native_free_buffers:
 report['limits'][-1]='At third virtual sleep, receiver CPU context is saved; original FreeBuffer and ReleaseBuffer execute on supplied matching header/slot records using a separate stack, then receiver resumes. Counters/slot usage cleared by native code. Header free/mutex services virtual; manual cooperative scheduling is not a real race/resource qualification.'
if args.spider_free_loop:
 report['limits'].append('Two-port case executes original SpiderApp235140 free loops on one input and ten output fixture headers, through native component FreeBuffer; stops at upper wait before resuming component. Starts after successful command prefix; full upper function entry/command/handle creation not executed.')
if args.upper_entry:
 report['limits'][-1]='Two-port case starts original SpiderApp2350c4 with wrapper requested-state1/component state2 fixtures. Native command submit, eleven frees and actual caller wait execute; receiver manually scheduled after enqueue/frees. Caller resumes through wait return to235200, before remaining handle cleanup. Services/allocation/queue/mutex virtual; no full lifecycle/APF/hardware qualification.'
if args.upper_finish:
 report['limits'][-1]='Two-port upper function2350c4 runs entry through command/frees, original notification/wait and final return. OMX_FreeHandle/Deinit calls virtual; flags supplied active. Native caller clears flags and returns0 even with injected FreeHandle failure, stored pointer unchanged. This is caller behavior, not proof of actual handle release or safe APF/hardware handoff.'
if args.native_core_free:
 report['core_sha256']='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
 report['spider_sha256']='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
 report['limits'][-1]='Two-port upper entry/command/frees/notification/wait continues through actual core FreeHandle and component DeInit/DestroyHandle back to original upper return. Core registry lookup/initialization, empty shared areas and OS/resource services supplied; JoinThread still virtual success. OMX_Deinit global API remains stub; no actual loader, thread exit, APF or hardware qualification.'
if args.native_core_thread_exit:
 report['limits'][-1]='Same three-binary sequence pauses at component join, resumes its saved original message-thread context on actual termination message, frees message and reaches exit service; only then models join success and resumes original core/upper return. Resource/OS exit/join/registry/scheduler services still virtual. OMX_Deinit global API remains stub; no real threads/APF/hardware qualification.'
if args.native_global_deinit:
 report['limits'][-1]='Same three-binary sequence also executes original core OMX_Deinit/OmfUninit after FreeHandle. Manager send/reply/thread/resource services supplied; native branch clears core/queue state and returns to original upper caller. No whole-function FreeHandle/Deinit stubs remain, but registration/state/OS/DSP/scheduler boundaries still virtual; no real APF/hardware qualification.'
(ROOT/'sources'/('native-spider-core-global-finish.json' if args.native_global_deinit else 'native-spider-core-component-thread-finish.json' if args.native_core_thread_exit else 'native-spider-core-component-finish.json' if args.native_core_free else 'native-spider-upper-finish-error.json' if args.free_handle_error else 'native-spider-upper-finish.json' if args.upper_finish else 'native-spider-upper-entry-notification.json' if args.upper_entry else 'native-spider-free-loop-notification.json' if args.spider_free_loop else 'native-h264-free-buffer-notification.json' if args.native_free_buffers else 'native-h264-loaded-notification.json' if args.target_loaded else 'native-h264-spider-notification.json' if args.spider_callback else 'native-h264-state-receiver.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Two original H264 state2->1 cases passed; native port-count wait precedes callback and bookkeeping follows callback' if args.target_loaded else 'Two original H264 receiver/state3->2 cases passed; stop/clear/unlock precede completion callback under virtual services')
