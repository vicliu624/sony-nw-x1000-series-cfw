"""Execute original view5 member transition and inspect its request boundary."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(raw)).get_section_by_name('.dynsym').iter_symbols()};cases=[]
for old_parent in (0,0x123400):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00;sp=area+0xf000;frame=area;counter=area+0x1000;parent=counter+4;selected=counter+8;native_parent=0x123500;requests=[];disposed=[];resolved=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(frame+4,5);put(frame+0x120,1);put(frame+8+28+8,0x321);put(counter,7);put(parent,old_parent)
 def hook(cpu,pc,size,data):
  if pc==done:cpu.emu_stop();return
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
  if pc==0x47370:value=0
  elif pc==0x41518:assert args[0]==0x77;value=0x88
  elif pc==symbols['MomaObjectId_dispose']:disposed.append(args[0])
  elif pc==0x428c4:
   dest=get(cpu.reg_read(UC_ARM_REG_SP));assert args==[0x88,0,0x321,4] and dest==parent
   put(dest,native_parent);resolved.append(True)
  elif pc==0x1f91c:
   stack=cpu.reg_read(UC_ARM_REG_SP);requests.append(args+[get(stack+i*4) for i in range(4)])
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(frame,4,0x77,counter)):u.reg_write(r,v)
 put(sp,parent);put(sp+4,selected);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(0x473b4,done+4,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==1
 assert len(requests)==1 and resolved==[True] and disposed==([old_parent] if old_parent else [])
 request=requests[0];assert request[0]==0x77 and request[1]==0 and request[2]==0x66e158+0xdfc and request[5:]==[1,native_parent,1]
 assert get(counter)==8 and get(frame+0x120)==2 and get(frame+8+2*28)==7
 cases.append(dict(replaced_parent=bool(old_parent),predicate_null=True,child_flag=1,parent_resolved_from_selected_row=True,member_sort='CHILDINDEX',depth_advanced=True))
report=dict(target_sha256=digest,cases=cases,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_list_transition.py').read_bytes()).hexdigest(),device_accessed=False,limits=['Original transition, node addressing and sort selection execute; row lookup, readiness and request submission are modeled.','This proves the view5 special member route, not visible menu binding, actual database contents or original-loader acceptance.'])
p=ROOT/'work/player-stock-list-transition';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
