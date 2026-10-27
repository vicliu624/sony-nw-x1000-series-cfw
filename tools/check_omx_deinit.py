"""Original OMX_Deinit/OmfUninit request/reply and teardown ordering; manager services virtual."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/libomx_core.so').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='865b7685bc54697c6e4dd9748d2ec6d4f1b2a5080ac4da8b974983cc6a4d6e6f'
elf=ELFFile(io.BytesIO(raw));rows=[]
for name,init,send,reply_error,terminate in (('success',1,0,0,0),('not-initialized',0,0,0,0),('send-fails',1,1,0,0),('reply-error',1,0,1,0),('thread-terminate-fails',1,0,0,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);ss=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in ss)&~4095;high=max((s['p_vaddr']+s['p_memsz']+4095)&~4095 for s in ss)
 u.mem_map(low,high-low)
 for s in ss:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 got=0x4df0+word(0x4edc)
 for slot,ptr,value in ((0x178,0x60001000,init),(0x1bc,0x60002000,0x60004000),(0x1e4,0x60003000,0x60005000)):
  put(got+slot,ptr);put(ptr,value)
 put(0x60006004,reply_error);put(0x60006010,0);calls=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if pc==0x21fc:uc.reg_write(UC_ARM_REG_PC,0x4ddc);return
  if pc==0x2460:
   assert a==[0x60004000,0x60005000,0xffffffff,0xfffffffe]
   assert bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_SP),16))==bytes(16)
   service='send_manager_uninit';ret=send
  elif pc==0x2454:
   assert a[1:3]==[0x60005000,0xffffffff];put(a[0],0x60006000);service='receive_reply';ret=0
  elif pc==0x2328:assert a[0]==0x60006000;service='free_reply';ret=0
  elif pc==0x2400:
   assert a[:2]==[0x60002000,0x60002004] and word(0x60001000)==0
   service='terminate_manager_thread';ret=terminate
  elif pc==0x2304:assert a[0]==0x60005000;service='destroy_reply_queue';ret=0
  elif pc==0x246c:service='destroy_communication_table';ret=0
  elif pc==0x222c:service='deinit_dsp_manager';ret=0
  elif pc==0x23d0:service='close_os_wrapper';ret=0
  else:return
  calls.append(service);uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 u.emu_start(0x5860,0x6001f000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
 result=0 if name=='success' else 0x80001001
 assert u.reg_read(UC_ARM_REG_R0)==result
 expected=[] if not init else ['send_manager_uninit']
 if init and not send:expected+=['receive_reply','free_reply']
 if init and not send and not reply_error:expected+=['terminate_manager_thread']
 if name=='success':expected+=['destroy_reply_queue','destroy_communication_table','deinit_dsp_manager','close_os_wrapper']
 assert calls==expected
 expected_flag=0 if not init or name in ('success','thread-terminate-fails') else 1
 assert word(0x60001000)==expected_flag
 assert word(0x60003000)==(0 if name=='success' else 0x60005000)
 rows.append({'case':name,'native_order':calls,'return':hex(result),'initialized_flag_after':word(0x60001000),'reply_queue_pointer_after':hex(word(0x60003000))})
report={'core_sha256':digest,'entry':'OMX_Deinit5860 -> original OmfUninit4ddc','cases':rows,
 'finding':'Global uninit sends manager command and waits for reply before thread/queue/DSP/OS teardown; no reference-count behavior established. Initialization flag clears before terminate-thread result.',
 'limits':['Global pointers/state and manager reply supplied; manager messaging/thread/resource services virtual. No actual manager processing, component-reference policy or real thread/DSP shutdown.',
           'Failure branches are original behavior, not firmware changes or safe-cleanup guarantees.']}
(ROOT/'sources/native-omx-deinit.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five original global OMX Deinit cases passed; manager reply gates teardown and failure state recorded')
