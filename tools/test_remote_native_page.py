"""Prototype Remote callbacks through Sony's original FSM and choice event map.

No ELF/UPG is installed. Resource/GUI, owner RPC and category leaves are modeled.
"""
import hashlib,io,json,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT

out=ROOT/'work/remote-native-page'/str(time.time_ns());out.mkdir(parents=True)
source='runtime/apps/wireless-remote/native_page.c'
linker=out/'page.ld'
linker.write_text('''ENTRY(wr_remote_page_open)
SECTIONS { . = 0x50000000; .text : { *(.text*) *(.rodata*) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
wr_remote_page_request = 0x7000fe00;
wr_page_post = 0xa57f0;
wr_page_parent = 0x7461c;
wr_page_index = 0x74608;
wr_page_set_category = 0x74668;
wr_page_set_state = 0x17ca34;
wr_page_stock_home = 0x7fb54;
wr_page_stock_playback = 0x73608;
''')
binary=out/'page.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(linker),source,'-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()))
symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
rows=[]
for case in ('open-refused','cancel','playback','home','apply-on','apply-off','apply-refused'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50000000,0x10000);u.mem_map(0x70000000,0x10000)
 for image in (ELFFile(io.BytesIO(raw)),helper):
  for segment in image.iter_segments():
   if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 area=0x70000000;context=area+0x100;master=area+0x3000;descriptor=area+0x4000;actions=area+0x4100;initializers=area+0x4200;done=area+0xff00
 u.mem_write(master,bytes(u.mem_read(0x3f55d8,193*4))+struct.pack('<I',descriptor))
 u.mem_write(descriptor,bytes(u.mem_read(0x4052e4,32)))
 u.mem_write(actions,bytes(u.mem_read(0x40542c,24*4)))
 for index,name in ((3,'confirm'),(4,'select'),(6,'playback'),(7,'home')):put(actions+index*4,symbols['wr_remote_page_'+name])
 put(descriptor+12,actions);put(descriptor+20,initializers)
 u.mem_write(initializers,struct.pack('<4I',symbols['wr_remote_page_init'],0,0,0))
 operations=[];posts=[];categories=[];applications=[];homes=[];preview=1
 def hook(cpu,pc,size,unused):
  global preview
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
  if pc==0x950f0:cpu.reg_write(UC_ARM_REG_PC,symbols['wr_remote_page_open']);return
  if pc==area+0xfe00:
   operation,row=args[:2];operations.append([operation,row])
   if operation==1:value=0x5752fffd if case=='open-refused' else 0x57530001
   elif operation==2:value=0x57530000|preview
   elif operation==3:assert row<=1;preview=row;value=0x57520000
   elif operation==4:
    applications.append(preview);value=0x5752fffc if case=='apply-refused' else 0x57520001
   elif operation==5:value=0x57520000
   else:raise AssertionError(operation)
  elif pc==0xa57f0:posts.append(args)
  elif pc==0x7461c:value=2
  elif pc==0x74608:value=11
  elif pc==0x74668:categories.append(args)
  elif pc==0x7fb54:homes.append(pc)
  elif pc in (0x17c42c,0x33b918,0x4aa60):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,args,extra=0):
  sp=area+0xe000;put(sp,extra)
  for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(register,value)
  u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(address,done,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 def event(code,value=0):assert call(0x17c608,[context,code,value,0])==0
 assert call(0x17c494,[context,194,master,2],2)==0
 event(0x4a0111,11)
 if case=='open-refused':
  assert list(u.mem_read(context,2))==[2,2] and not posts and not applications
 else:
  assert list(u.mem_read(context,2))==[194,1]
  assert posts==[[0x20106,0,29,1]] and categories==[[2,194,0,11]] and not applications
  event(0x4a0116)
  assert list(u.mem_read(context,2))==[194,2]
  event(0x4a0111,1 if case=='apply-off' else 0)
  assert not applications
  if case=='playback':event(0x4a011b)
  elif case=='home':event(0x4a0110)
  else:event(0x4a0119,0xff0001 if case=='cancel' else 0xff0000)
  assert list(u.mem_read(context,2))==([194,2] if case=='apply-refused' else [51,1] if case=='home' else [56,4] if case=='playback' else [2,1])
  if case not in ('home','playback','apply-refused'):
   assert posts[-1]==[0x20106,0,97,11] and categories[-1]==[0,2,0,11]
   event(0x4a0116)
   assert list(u.mem_read(context,2))==[2,2]
  assert applications==([1 if case=='apply-off' else 0] if case.startswith('apply-') else [])
  assert len(homes)==int(case=='home')
 rows.append(dict(case=case,final_state=list(u.mem_read(context,2)),operations=operations,apply_rows=applications,page_requests=posts))
report=dict(passed=True,cases=rows,original_fsm_and_choice_event_map=True,actual_native_c_callbacks=True,
 device_accessed=False,firmware_created=False,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (source,'runtime/apps/wireless-remote/native_page.h','tools/test_remote_native_page.py')},
 limits=['Registration table/count are supplied to original constructor; production startup is not patched.',
         'GUI/resource loader, category leaves and owner request bridge are modeled; no physical display/RF acceptance.',
         'Playback shortcut executes original73608 and group56 initializer; its playback service leaf is modeled.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
