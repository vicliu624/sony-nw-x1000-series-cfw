"""Replay original Met worker loop/event wait; no sequence read or new hook."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R7
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for queued in (False,True):
 for timed_out in (False,True):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
  area=0x71000000;u.mem_map(area,65536)
  service,session,player,data,message,event,done=(area+x for x in (0,0x2000,0x3000,0x4000,0x5000,0x6000,0x7000))
  def put(a,v):u.mem_write(a,struct.pack('<I',v))
  def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  put(session+0x20,player);put(session+0x1c,data);put(message+4,0x31);put(message+8,session);put(message+12,2)
  calls=[];pops=[0];retains=[0];releases=[0];registered=[0];node=[0]
  def hook(uc,pc,size,context):
   def finish(value=0):uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
   r0,r1,r2=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
   if pc==done:uc.emu_stop();return
   if pc==0x27c610:assert uc.reg_read(UC_ARM_REG_R7)==service+0xec8
   if pc==0x3355ac:finish(event);return
   if pc==0x286174:assert r0==service+4;finish(1);return
   if pc==0x286200:
    assert r0==service+4
    if queued and not pops[0]:pops[0]=1;finish(message)
    else:put(r1,0x123);finish(0)
    return
   if pc==0x27b1b8:assert (r0,r1)==(player,message+12);calls.append('command');finish();return
   if pc==0x276544:assert (r0,r1,r2)==(data,0x31,0);calls.append('ack');finish();return
   if pc==0x2862b8:assert (r0,r1)==(service+4,message);finish();return
   if pc==0x27b614:assert r0==service+0xec8;retains[0]+=1;finish(session);return
   if pc==0x27b640:assert (r0,r1)==(service+0xec8,session);finish(0);return
   if pc==0x27b7f8:assert (r0,r1)==(service+0xec8,session);releases[0]+=1;finish();return
   if pc==0x27b334:assert (r0,r1,r2)==(player,0x123,1);calls.append('poll');finish();return
   if pc==0x276534:assert r0==data;finish();return
   if pc==0x337e74:assert r0==event;finish();return
   if pc==0x336648:assert r0==0x123 and not registered[0];registered[0]=1;node[0]=r1;finish();return
   if pc==0x337ea0:assert (r0,r1)==(event,1000) and registered[0];calls.append('wait');finish(0x105 if timed_out else 0);return
   if pc==0x336744:assert (r0,r1)==(0x123,node[0]) and registered[0];registered[0]=0;finish();return
   if pc==0x27b404:assert (r0,r1)==(player,0x123);calls.append('prefetch');finish();return
   if pc==0x2860d0:assert r0==service+4;finish();return
   if pc==0x336174:finish();return
   if pc==0x337dd4:assert r0==event and not registered[0];finish();return
  u.hook_add(UC_HOOK_CODE,hook)
  u.reg_write(UC_ARM_REG_R0,service);u.reg_write(UC_ARM_REG_SP,area+65520);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(0x27c45c,done+4,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
  expected=(['command','ack'] if queued else [])+['poll','wait']+(['prefetch'] if timed_out else [])
  assert calls==expected,(queued,timed_out,calls)
  assert retains[0]==1+int(timed_out) and releases[0]==retains[0]+int(queued) and not registered[0]
  cases.append(dict(queued=queued,event_wait_timeout=timed_out,calls=calls,session_list_get_calls=retains[0],session_release_calls=releases[0],cancellation_registration_balanced=True))
w=ROOT/'work/stock-met-owner';w.mkdir(exist_ok=True)
report=dict(passed=True,original_service_loop=True,original_session_wrappers=True,original_wait_adapter=True,cases=cases,device_accessed=False,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_met_owner.py').read_bytes()).hexdigest(),stock_sha256=hashlib.sha256(raw).hexdigest(),limits=['Queue/events/session-list primitives, raw player processing and cancellation registration are modeled.','Original Met service ordering, command/session pointer forwarding and timeout branch execute; no real queue contents, locks or hardware are qualified.','No owner-thread patch, sequence snapshot or endpoint queue backend is introduced.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
