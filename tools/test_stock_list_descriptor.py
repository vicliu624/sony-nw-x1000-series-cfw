"""Original view5 descriptor extraction; no compiler, device or database IO."""
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
 if s['p_type']!='PT_LOAD':continue
 a=int(s['p_vaddr']); b=a&~4095
 u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
area=0x71000000;u.mem_map(area,65536);done=area+0xff00;base=0x66e158;stop=[None];mapping_mode=[False];bindings=[];navigation_mode=[False];notifications=[]
def hook(cpu,pc,size,data):
 if navigation_mode[0] and pc in (0x1f150,0xa57f0):
  if pc==0xa57f0:notifications.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
  cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
 if mapping_mode[0]:
  instruction=struct.unpack('<I',cpu.mem_read(pc,4))[0]
  if instruction&0x0f000000==0x0b000000:
   displacement=(instruction&0xffffff)<<2
   if displacement&0x2000000:displacement-=0x4000000
   target=(pc+8+displacement)&0xffffffff
   if target==0x435a4:
    bindings.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
   else:
    cpu.reg_write(UC_ARM_REG_R0,0);cpu.reg_write(UC_ARM_REG_PC,pc+4);return
 if pc==0xb93a0 and cpu.reg_read(UC_ARM_REG_R2)==base+0xdfc:stop[0]=cpu.reg_read(UC_ARM_REG_LR)
 if pc==stop[0] or pc==done:cpu.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,*args):
 sp=area+0xf000
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
 for i,v in enumerate(args[4:]):u.mem_write(sp+i*4,struct.pack('<I',v))
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done+4,count=100000)
call(0x47cac,base);assert stop[0] and u.reg_read(UC_ARM_REG_PC)==stop[0];stop[0]=None
frame=area+0x1000;u.mem_write(frame+4,struct.pack('<I',5));outputs=[area+0x2000+i*4 for i in range(5)];rows=[]
for depth in (1,2):
 call(0x46d74,frame+8,5,0xffffffff,0xffffffff);assert u.reg_read(UC_ARM_REG_PC)==done
 for a in outputs:u.mem_write(a,b'\xa5'*4)
 call(0x47268,frame,*outputs);assert u.reg_read(UC_ARM_REG_PC)==done
 values=[struct.unpack('<I',u.mem_read(a,4))[0] for a in outputs]
 expected_predicate=base+(0x4e8 if depth==1 else 8)
 assert values[0]==expected_predicate,(depth,values)
 assert values[3]==base+(0xa88 if depth==1 else 0xdfc)
 assert values[4]==0
 rows.append(dict(depth=depth,predicate=hex(values[0]),raw_descriptor_pointer=hex(values[1]),raw_descriptor_auxiliary=values[2],sort=hex(values[3]),auxiliary=values[4]))
# Execute original category-to-view writes separately. Other initialization calls
# are skipped: this checks mapping, not complete application startup.
selection_frame=area+0x3000;selection_views=[]
for index in range(10):
 u.mem_write(selection_frame,struct.pack('<II',0,0xffffffff))
 call(0x434dc,selection_frame,index);assert u.reg_read(UC_ARM_REG_PC)==done
 selection_views.append(struct.unpack('<I',u.mem_read(selection_frame+4,4))[0])
assert selection_views==list(range(10))
mapping_frame=area+0x4000;mapping_mode[0]=True
call(0x435e8,mapping_frame);mapping_mode[0]=False
assert u.reg_read(UC_ARM_REG_PC)==done
assert (5,1,17) in bindings and (5,2,18) in bindings
for category,depth,view in bindings:
 assert struct.unpack('<I',u.mem_read(mapping_frame+depth*0x1c+category*0x124+0x50,4))[0]==view
# Enter menu index5 through the original kind0 selector and view-reset chain.
# Rendering/reset notification consumers are modeled, query selection is not.
navigation_mode[0]=True
call(0x44408,mapping_frame,0,5,0xffffffff);navigation_mode[0]=False
assert u.reg_read(UC_ARM_REG_PC)==done
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
active_frame=mapping_frame+5*0x124+0x30
assert get(mapping_frame+4)==0 and get(mapping_frame+0xc)==5
assert get(active_frame+4)==5 and get(active_frame+0x120)==1
assert get(active_frame+12)==base+0x4e8
assert len(notifications)==1 and notifications[0][2]==5
report=dict(target_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256((ROOT/'tools/test_stock_list_descriptor.py').read_bytes()).hexdigest(),rows=rows,selector_kind0_indices0_to9=selection_views,kind0_index5_enters_format3_view=True,category5_depth_views=[17,18],category_mapping_writes_verified=len(bindings),device_accessed=False,limits=['Original query initializer prefix, selector, descriptor and sort helpers execute without modeled native calls.','Category initializer and mapping writes execute; unrelated startup calls are skipped.','Kind0/index5 entry executes original selection/reset/query chain; renderer/reset notification consumers are modeled.','The fifth descriptor output is an auxiliary per-view value, not proof of the child-query flag.','Projection descriptor initialization is outside the executed prefix; its two raw outputs are not qualified here.','Selector kind0/index5 maps to view5; its active resource event binding remains unqualified.'])
p=ROOT/'work/player-stock-list-descriptor';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
