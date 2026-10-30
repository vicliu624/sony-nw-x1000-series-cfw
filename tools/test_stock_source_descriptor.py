"""Original source-description copy and local item ownership transfer."""
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
image=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in image.get_section_by_name('.dynsym').iter_symbols()}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for segment in image.iter_segments():
 if segment['p_type']!='PT_LOAD':continue
 a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
area=0x71000000;u.mem_map(area,65536);audio=area;source=area+0x1000;heaps=[area+0x2000,area+0x2100,area+0x2200];old_id=area+0x3000;first=area+0x3100;second=area+0x3200;done=area+0xff00
refs={old_id:1,first:1,second:1};live=[];freed=[];updates=[];clone_calls=[]
def put(a,v):u.mem_write(a,struct.pack('<I',v))
def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
counter=get(0x4abcc);assert counter==get(0x4aac4);put(counter,0);put(audio+4,old_id)
def hook(uc,pc,size,context):
 r0,r1=(uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1))
 def finish(v=0):uc.reg_write(UC_ARM_REG_R0,v);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 if pc==symbols['malloc']:
  assert r0==64;block=heaps[len(live)+len(freed)];live.append(block);finish(block);return
 if pc==symbols['free']:assert r0 in live;live.remove(r0);freed.append(r0);finish();return
 if pc==0x2995e8:assert r0 in refs and refs[r0]>0;refs[r0]-=1;finish();return
 if pc==0x2995d0:clone_calls.append(r0);raise AssertionError('Unexpected ID clone in move path')
 if pc==0xac8e4:assert r0==audio;updates.append(get(audio+4));finish();return
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,*args):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done;return u.reg_read(UC_ARM_REG_R0)
for index,item in enumerate((first,second)):
 words=[0,item]+[0]*14;u.mem_write(source,struct.pack('<16I',*words));assert call(0xad270,audio,source)==0
 pending=get(audio+8);assert pending in live and bytes(u.mem_read(pending,64))==struct.pack('<16I',*words)
 u.mem_write(source,bytes(64));assert get(pending+4)==item and get(audio+4)==item and refs[item]==1
 assert refs[old_id if not index else first]==0 and get(counter)==1
 assert updates[-1]==item and not clone_calls
# Original selected-ID setter releases its current owned ID; descriptor free is separate.
call(0xacb20,audio,0);assert refs=={old_id:0,first:0,second:0};call(0x4aaa8,get(audio+8));put(audio+8,0)
assert not live and get(counter)==0 and len(freed)==2
w=ROOT/'work/stock-source-descriptor';w.mkdir(exist_ok=True)
report=dict(passed=True,device_accessed=False,original_copy_install_replace_and_free=True,descriptor_bytes=64,input_buffer_may_expire_after_copy=True,new_id_is_moved_not_cloned=True,previous_selected_id_released=True,descriptor_allocation_counter_balanced=True,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_source_descriptor.py').read_bytes()).hexdigest(),limits=['malloc/free, ID disposal and UI update helper modeled; original descriptor/copy/replace/free instructions execute.','This is not the complete GUI event/source consumer lifecycle or an OOM qualification; PLAY_ITEM remains disabled.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
