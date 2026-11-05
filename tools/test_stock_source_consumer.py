"""Original source request consumer releases its message-owned sequence."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for result in (0,0x106,0x2604,0x2202):
 for has_sequence in (False,True):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for s in ELFFile(io.BytesIO(raw)).iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  area=0x71000000;u.mem_map(area,65536);session=area;payload=area+0x1000;sequence=area+0x2000;player=area+0x3000;reply=area+0x4000;done=area+0xff00;calls=[];responses=[]
  def put(a,v):u.mem_write(a,struct.pack('<I',v))
  def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
  put(session+0x18,0x4321);put(session+0x1c,reply);put(session+0x20,player);put(payload,1);put(payload+24,sequence if has_sequence else 0);put(sequence,2)
  def hook(cpu,pc,size,data):
   if pc==done:cpu.emu_stop();return
   args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3));value=0
   if pc==0x27b1b8:assert args[:2]==(player,payload);calls.append('apply');value=result
   elif pc==0x27e888:assert args[:2]==(sequence,session+0x30);calls.append('observer')
   elif pc==0x27e8b4:assert args[:2]==(sequence,0x4321);calls.append('context')
   elif pc in (0x27b4a0,0x27b4b0,0x335788,0x3357e4):pass
   elif pc==0x27afa4:assert args[0]==player;value=9
   elif pc==0x276544:assert args[:3]==(reply,77,result);responses.append(args[:3])
   else:return
   cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),(session,77,payload)):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x27bba4,done+4,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==result
  assert get(sequence)==(1 if has_sequence else 2) and get(session+0x10)==9
  assert calls==(['observer','context','apply'] if has_sequence else ['apply']) and len(responses)==1
  cases.append(dict(result=result,sequence_present=has_sequence,message_reference_released=has_sequence,completion_ticket=77,completion_result_preserved=True))
report=dict(target_sha256=digest,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_consumer.py').read_bytes()).hexdigest(),cases=cases,device_accessed=False,limits=['Original session consumer and sequence-release instructions execute.','Player command/state observation, sequence observer attachment, mutex/context gates and completion notification are modeled.','Fatal0x2683 branch and full player FSM/source installation are not qualified; PLAY_ITEM remains disabled.'])
p=ROOT/'work/player-stock-source-consumer';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
