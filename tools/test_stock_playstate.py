"""Original controller target-state processing and playback-apply branch replay.

Synchronization, FSM dispatch, data access/publication, logging and raw-player
operations are modeled. The original message-processing and apply instructions
execute. No audio output, device access or public service availability is proved.
"""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/stock-playstate';work.mkdir(exist_ok=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(stock));cases=[]
for request,target in ((1,0),(2,1)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for segment in elf.iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  address=int(segment['p_vaddr']);base=address&~4095
  u.mem_map(base,(address-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(address,segment.data())
 stack,area,done=0x70000000,0x71000000,0x72000000
 u.mem_map(stack,65536);u.mem_map(area,131072);u.mem_map(done,4096)
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 player,frame,options,actor,track=area,area+0x8000,area+0x8100,area+0x8200,area+0x8300
 put(frame,request);put(frame+4,options);put(options,target);put(options+4,1)
 put(player+0x3ca4,area+0x10000);put(player+0x3ca0,area+0x11000);put(actor,player);put(track,123)
 published=[];raw=[];stage='process'
 def finish(value=0):u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 def hook(uc,pc,size,data):
  if pc==done:uc.emu_stop();return
  if pc==0x2767b0:
   dest=uc.reg_read(UC_ARM_REG_R1);u.mem_write(dest,bytes(0x5c));put(dest,target if stage=='apply' else 0);put(dest+0xc,123);finish();return
  if pc==0x27b004:finish(0x20);return
  if pc==0x276c78:
   assert uc.reg_read(UC_ARM_REG_R0)==area+0x10000
   published.append(uc.reg_read(UC_ARM_REG_R1));finish();return
  if pc in (0x286aa4,0x286af4,0x286458,0x2864c4,0x276c3c,0x286468,0x27b0b8,0x278444):finish();return
  if pc==0x277950:finish(2);return
  if pc==0x2776d0:finish(track);return
  if pc==0x278da4:raw.append('pause');finish();return
  if pc==0x277b10:raw.append('prepare-pause');finish();return
  if pc==0x277c00:raw.append('play');finish();return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,*arguments):
  u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,done)
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),arguments):u.reg_write(reg,value)
  u.emu_start(address,done+4,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 assert call(0x27b1b8,player,frame)==0
 assert published==[target]
 stage='apply'
 assert call(0x27a5fc,actor,0)==0
 assert raw==(['pause'] if target==1 else ['prepare-pause','play']),raw
 cases.append(dict(controller_request=request,option_target=target,published_target=published[0],native_apply_path=raw))
report=dict(passed=True,device_accessed=False,original_message_processing=True,original_apply_branches=True,
            actual_audio_output=False,cases=cases,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limits=['FSM dispatch, data access/publication, synchronization, logging and raw playback operations are modeled.',
                    'This establishes target-state semantics, not a live playback-state snapshot or completion notification.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
