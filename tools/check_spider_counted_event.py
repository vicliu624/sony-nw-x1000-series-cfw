"""Original counted condition event used by AVC cleanup; no live threads."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for posts in (0,1,2):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);event=0x60001000;calls=[]
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 def hook(uc,pc,size,data):
  if pc==symbols['pthread_cond_wait'] or pc==symbols['pthread_cond_timedwait']:raise AssertionError('Unexpected blocking wait')
  for name in ('pthread_mutex_lock','pthread_mutex_unlock','pthread_cond_signal'):
   if pc==symbols[name]:
    assert uc.reg_read(UC_ARM_REG_R0)==(event if name=='pthread_cond_signal' else event+0x30)
    calls.append(name);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(entry,timeout=0):
  u.reg_write(UC_ARM_REG_R0,event);u.reg_write(UC_ARM_REG_R1,timeout&0xffffffff)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
  u.emu_start(entry,0x6001f000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
  return u.reg_read(UC_ARM_REG_R0)
 for i in range(posts):call(0x23d7ec)
 assert word(event+0x48)==posts and calls.count('pthread_cond_signal')==int(posts>0)
 results=[call(0x23d718,-1) for _ in range(posts)]
 assert results==[1]*posts and word(event+0x48)==0
 assert call(0x23d718,0)==0 and word(event+0x48)==0
 component_path=None
 if posts==1:
  owner=0x60004000;ctx=owner+0x7b0
  u.mem_write(owner+0x7bc,struct.pack('<I',event));u.mem_write(owner+0x7c8,struct.pack('<I',owner))
  u.reg_write(UC_ARM_REG_R6,owner);u.reg_write(UC_ARM_REG_SP,0x60018000)
  u.emu_start(0x234dd4,symbols['OMX_GetHandle'],count=1000)
  assert u.reg_read(UC_ARM_REG_PC)==symbols['OMX_GetHandle']
  assert u.reg_read(UC_ARM_REG_R0)==owner+0x74c
  assert u.reg_read(UC_ARM_REG_R2)==ctx and u.reg_read(UC_ARM_REG_R3)==owner+0x750
  callback=word(owner+0x750);assert callback==0x234a68
  name=bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),80)).split(b'\0')[0].decode()
  for event_code in (2,0):
   u.reg_write(UC_ARM_REG_R0,0x60003000);u.reg_write(UC_ARM_REG_R1,ctx)
   u.reg_write(UC_ARM_REG_R2,event_code);u.reg_write(UC_ARM_REG_R3,0)
   u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
   u.emu_start(callback,0x6001f000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x6001f000 and word(event+0x48)==int(event_code==0)
  assert call(0x23d718,-1)==1 and word(event+0x48)==0
  component_path={'registration_prefix':'0x234dd4 -> OMX_GetHandle boundary','component_name_from_original_literal':name,
                  'callback_from_original_table':hex(callback),'appdata':'owner+0x7b0','event':'owner+0x7bc',
                  'manually_delivered_event2_posts':0,'manually_delivered_event0_posts':1,'native_wait_consumes_notification':True}
 rows.append({'native_posts':posts,'condition_signals':calls.count('pthread_cond_signal'),'preposted_infinite_wait_results':results,'empty_nonblocking_result':0,'count_after':0,'native_component_notification_path':component_path})
report={'input_sha256':digest,'procedures':{'post':'0x23d7ec','wait':'0x23d718'},'cases':rows,
 'finding':'Native post increments count; condition signal only on0-to1. Wait consumes one token and returns1, including timeout-1 with preposted token; empty timeout0 returns0.',
 'limits':['Event storage supplied; pthread lock/unlock/signal virtual. No blocking cond_wait, thread scheduling or real component notification.',
           'Extra sample executes native OMX registration prefix to API boundary, manually delivers registered callback events2/0, then native post/wait. GetHandle/component/thread dispatch is not executed; event0 notification alone does not prove requested state completion.']}
(ROOT/'sources/native-spider-counted-event.json').write_text(json.dumps(report,indent=2)+'\n')
print('Three native event token cases passed: posts0/1/2, preposted waits consume, empty poll returns0; no live notification claim')
