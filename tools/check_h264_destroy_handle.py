"""Original H264 handle destruction ordering; queue/thread/resources are virtual."""
from pathlib import Path
import hashlib,io,json,struct,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--native-thread-exit',action='store_true');parser.add_argument('--component-deinit',action='store_true');parser.add_argument('--omx-core',action='store_true');args=parser.parse_args()
assert not args.omx_core or args.component_deinit
raw=(ROOT/'work/targets-jp/omf_mc_h264d.so').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='8dcb6f2c5cd5a107e3f84daa1f8a72ef420abf59c67bc7281b9ab10d2536a8b2'
elf=ELFFile(io.BytesIO(raw));rows=[]
for name,allocation,post_result in (('accepted',0x60003000,0),('allocation-fails',0,0),('queue-rejects',0x60003000,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 if args.omx_core:
  core_raw=(ROOT/'work/targets-jp/libomx_core.so').read_bytes()
  assert hashlib.sha256(core_raw).hexdigest()=='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
  core=ELFFile(io.BytesIO(core_raw));core_base=0x20000000
  cs=[s for s in core.iter_segments() if s['p_type']=='PT_LOAD']
  cl=min(s['p_vaddr'] for s in cs)&~4095;ch=max((s['p_vaddr']+s['p_memsz']+4095)&~4095 for s in cs)
  u.mem_map(core_base+cl,ch-cl)
  for s in cs:u.mem_write(core_base+s['p_vaddr'],s.data())
  got=core_base+0x5aa0+word(core_base+0x5b24)
  put(got+word(core_base+0x5b28),0x6000a000);put(0x6000a000,1)
  put(0x6000104c,0x28d4)
  for off,v in ((4,1),(0x10,0x60001000),(0x40,0x6000c000)):put(0x6000b000+off,v)
 for p,v in ((0x60001008,0x60002000),(0x600023dc,0x60004000),(0x600023cc,0x60005000),
             (0x600023d0,0x60005004),(0x600023d4,0x60005008),(0x600023d8,0x60006000)):put(p,v)
 if args.component_deinit:
  for p,v in ((0x6000200c,1),(0x600023c8,0x61000000),(0x600023c0,0x1000),(0x600020f0,2),(0x6000201c,0x60007000)):put(p,v)
  for port in range(2):
   record=0x600020f4+port*0x164;put(record+4,0x62000000+port*0x1000);put(record+8,0x1000)
 calls=[];thread_phase=False;thread_calls=[];thread_exit_requested=False
 def hook(uc,pc,size,data):
  global thread_exit_requested
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
  if args.omx_core and pc==core_base+0x2208:
   assert a[0]==0x60001000;calls.append('core_lookup')
   uc.reg_write(UC_ARM_REG_R0,0x6000b000);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.omx_core and pc==core_base+0x22a4:
   assert a[0] in (0x60001000,0x6000c000) and word(0x6000b004)==0
   calls.append('core_free_handle' if a[0]==0x60001000 else 'core_free_auxiliary')
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if thread_phase:
   if pc==0x17b4:
    assert a[1]==0x60004000;put(a[0],0x60003000);thread_calls.append('receive_termination');ret=0
   elif pc==0x16ac:
    assert a[0]==0x60003000;thread_calls.append('free_termination_message');ret=0
   elif pc==0x1748:
    assert a[0]==0;thread_calls.append('request_thread_exit');thread_exit_requested=True;uc.emu_stop();return
   else:return
   uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.component_deinit and pc in (0x15d4,0x1700):
   uc.reg_write(UC_ARM_REG_PC,0x2858 if pc==0x15d4 else 0x26f8);return
  if args.component_deinit and pc==0x17c0:
   assert a in ([0x61000000,0x1000],[0x62000000,0x1000],[0x62001000,0x1000])
   calls.append('unmap_shared');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.component_deinit and pc==0x16ac and a[0]==0x60007000:
   calls.append('free_frame_buffer');uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0x161c:assert a[0]==12;service='allocate';ret=allocation
  elif pc==0x170c:
   assert a==[0x60004000,0x60003000] and word(a[1])==0x7fffffff
   service='post_termination';ret=post_result
  elif pc==0x1820:
   assert a[0]==0x60006000;service='join_thread';ret=0
   if args.native_thread_exit:calls.append(service);uc.emu_stop();return
  elif pc==0x16e8:assert a[0]==0x60004000;service='destroy_queue';ret=0
  elif pc==0x17e4:assert a[0] in (0x60005000,0x60005004);service='destroy_mutex';ret=0
  elif pc==0x1730:assert a[0]==0x60005008;service='destroy_signal';ret=0
  elif pc==0x16ac:assert a[0]==0x60002000;service='free_private';ret=0
  else:return
  calls.append(service);uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.reg_write(UC_ARM_REG_R0,0x60001000);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(core_base+0x5a8c if args.omx_core else 0x28d4 if args.component_deinit else 0x2858,0x6001f000,count=10000)
 if args.native_thread_exit and allocation and not post_result:
  assert u.reg_read(UC_ARM_REG_PC)==0x1820
  saved=u.context_save();resume=u.reg_read(UC_ARM_REG_LR);thread_phase=True
  u.reg_write(UC_ARM_REG_R0,0x60001000);u.reg_write(UC_ARM_REG_SP,0x60016000);u.reg_write(UC_ARM_REG_LR,0x6001e000)
  u.emu_start(0x32fc,0,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x1748 and thread_exit_requested
  assert thread_calls==['receive_termination','free_termination_message','request_thread_exit']
  thread_phase=False;u.context_restore(saved);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,resume)
  u.emu_start(resume,0x6001f000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000 and u.reg_read(UC_ARM_REG_R0)==0
 expected=['allocate']+(['post_termination'] if allocation else [])+(['join_thread'] if allocation and not post_result else [])+['destroy_queue','destroy_mutex','destroy_mutex','destroy_signal','free_private']
 if args.component_deinit:expected=['unmap_shared']*3+['free_frame_buffer']+expected
 if args.omx_core:expected=['core_lookup']+expected+['core_free_handle','core_free_auxiliary']
 assert calls==expected
 if args.omx_core:assert all(word(0x6000b000+off)==0 for off in (4,0x10,0x40))
 rows.append({'case':name,'native_order':calls,'return':0,'stored_private_pointer_after':hex(word(0x60001008)),'original_thread_order':thread_calls,'original_thread_exit_requested':thread_exit_requested})
report={'component_sha256':digest,'entry':'OmfMcDestroyHandle0x2858','cases':rows,
 'finding':'Accepted termination message7fffffff is followed by JoinThread before queue/mutex/signal/private destruction. Allocation/post failure skips join and still returns0 after cleanup.',
 'limits':['Handle/resource fields supplied. Allocation, queue, thread join and resource destruction are virtual; no actual command thread exit or memory reclamation.',
           'This is stock component behavior, not a change or a guarantee of safe failure cleanup. OMX_FreeHandle core wrapper and full APF return are outside scope.']}
if args.native_thread_exit:
 report['limits'].append('Accepted case pauses at JoinThread, manually schedules original message-thread body on separate stack to consume actual termination message, frees it and reaches OmfExitThread(0). Stops at exit service, then models join success and resumes destructor. Actual OS thread exit/join/scheduling remain unqualified.')
if args.component_deinit:
 report['entry']='OmfMcComponentDeInit0x28d4 -> original shared-area helpers -> DestroyHandle'
 report['limits'].append('Component state1/two ports/shared mappings/frame buffer are fixtures. Native deinit unmaps areas and frees frame buffer before DestroyHandle; unmap/free services virtual. Other active states are not covered; do not generalize DestroyHandle join-first order to all deinit resources.')
if args.omx_core:
 report['core_sha256']='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
 report['entry']='Rebased OMX core FreeHandle -> native H264 ComponentDeInit -> DestroyHandle -> native return -> core record cleanup'
 report['limits'].append('Core mapped at20000000; initialization and registry lookup supplied. Component callback is actual original28d4, not success stub; core cleanup follows native component return. OS/resource services and join still virtual; no real loader/unload or APF/hardware qualification.')
(ROOT/'sources'/('native-omx-core-component-destroy.json' if args.omx_core else 'native-h264-component-deinit-thread.json' if args.component_deinit and args.native_thread_exit else 'native-h264-component-deinit.json' if args.component_deinit else 'native-h264-destroy-thread-exit.json' if args.native_thread_exit else 'native-h264-destroy-handle.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Three original H264 DestroyHandle cases passed; join ordering and failure-path bypass recorded under virtual services')
