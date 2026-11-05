"""Original APF activation/inactivation result and local commit, no device."""
import hashlib,io,json,struct
from itertools import product
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for segment in ELFFile(io.BytesIO(raw)).iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
area=0x60000000;u.mem_map(area,0x20000);client=area+0x1000;done=area+0x1f000
def put(a,v):u.mem_write(a,struct.pack('<I',v))
def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
packets=[];send_error=receive_error=reply_error=0;locks=[]
def hook(cpu,pc,size,unused):
 if pc in (0x337a80,0x337ae8):locks.append(pc);answer=0
 elif pc==0x268c9c:
  assert cpu.reg_read(UC_ARM_REG_R0)==500 and cpu.reg_read(UC_ARM_REG_R1)==55 and cpu.reg_read(UC_ARM_REG_R3)==24
  packets.append(list(struct.unpack('<6I',cpu.mem_read(cpu.reg_read(UC_ARM_REG_R2),24))));answer=send_error
 elif pc==0x268d48:
  assert cpu.reg_read(UC_ARM_REG_R0)==500 and cpu.reg_read(UC_ARM_REG_R2)==16
  cpu.mem_write(cpu.reg_read(UC_ARM_REG_R1),struct.pack('<4I',16,5,1,reply_error));answer=receive_error
 elif pc in (0x265298,0x33b83c):answer=0
 else:return
 cpu.reg_write(UC_ARM_REG_R0,answer);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[]
for initial,desired,send_error,receive_error,reply_error in product((0,1,2),(0,1,2),(0,16),(0,17),(0,18)):
 u.mem_write(client,bytes(48))
 for offset,value in ((0,1),(4,initial),(12,55),(16,500),(20,5),(40,1)):put(client+offset,value)
 packets.clear();locks.clear()
 for reg,value in ((UC_ARM_REG_R0,client),(UC_ARM_REG_R1,desired),(UC_ARM_REG_SP,area+0x1e000),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
 u.emu_start(0x2680a8,done,count=30000);assert u.reg_read(UC_ARM_REG_PC)==done
 current_logical=0 if initial==2 else 1
 attempted=initial!=0 and desired in (0,1) and current_logical!=desired
 target=2 if desired==0 else 1
 expected=0x1d09 if initial==0 else 0x102 if desired==2 else (send_error or receive_error or reply_error) if attempted else 0
 assert u.reg_read(UC_ARM_REG_R0)==expected
 assert packets==([[24,5,1,1,55,target]] if attempted else [])
 assert get(client+20)==(6 if attempted else 5)
 assert get(client+4)==(target if attempted and not expected else initial)
 assert locks.count(0x337a80)==locks.count(0x337ae8)
 rows.append(dict(initial_state=initial,logical_request=desired,send_result=send_error,receive_result=receive_error,reply_result=reply_error,return_value=expected,request_sent=attempted,final_state=get(client+4)))
print(json.dumps(dict(passed=True,arm_cases=len(rows),device_accessed=False,firmware_created=False,stock_sha256=digest,cases=rows,source_hashes={'tools/test_stock_activation_confirm.py':hashlib.sha256((ROOT/'tools/test_stock_activation_confirm.py').read_bytes()).hexdigest()},limits=['Original state-confirmation method and logical-state getter execute; mutex, transport and log boundaries are fixtures.','No physical manager reply, transport framing/security, SDK resume binding, RF power or sleep/USB qualification.']),indent=2))
