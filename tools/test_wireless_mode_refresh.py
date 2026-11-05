"""Actual confirm -> Sony FSM -> actual three-choice initializer replay.

Original binary confirm/init execute. Mode authority, NVP reads, UI properties,
category operations and queue delivery remain explicit fixtures; no RF/device.
"""
import argparse,hashlib,io,json,struct,subprocess,tarfile,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--firmware-review',help='Execute the exact callbacks and tables from a reviewed UPG')
args=parser.parse_args()
out=ROOT/'work/wireless-mode-refresh'/str(time.time_ns());out.mkdir(parents=True)
linker=out/'refresh.ld';binary=out/'refresh.arm'
linker.write_text('''ENTRY(xw_wireless_native_confirm)
SECTIONS { . = 0x50000000; .text : { *(.text*) *(.rodata*) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
xw_native_mode_request = 0xda84; xw_mode_request = 0xda84;
xw_native_stock_confirm = 0x88494; xw_mode_stock_init = 0x88400;
xw_native_selected_row = 0x4ee5d8; xw_mode_selected = 0x4ee5d8;
xw_mode_ui_root = 0x2a984; xw_mode_param_get = 0x10a118;
xw_mode_param_set = 0x10a0d4; xw_mode_post = 0xa57f0;
xw_mode_parent = 0x7461c; xw_mode_index = 0x74608; xw_mode_category = 0x74668;
''')
sources=['runtime/platform/wireless/native_callback.c','runtime/platform/wireless/native_mode_init.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(linker),*sources,'-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
firmware_sha=None
images=[ELFFile(io.BytesIO(raw)),helper]
if args.firmware_review:
 from prepare_managed_firmware_review import unpack
 _,review=receipt(args.firmware_review)
 path=private(review['artifact']);firmware_sha=digest(path)
 assert firmware_sha==review['sha256'] and review['final_root_inventory_verified']
 layout_path=next(name for name in review['inputs'] if '/player-system-layout/' in name)
 _,layout=receipt(layout_path)
 wireless=layout['host_build']['wireless_composition']
 _,parts=unpack(path.read_bytes(),require_stock=False)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
  raw=archive.extractfile('./usr/local/lib/x1000-player/SpiderApp').read()
 assert hashlib.sha256(raw).hexdigest()==layout['host_build']['candidate_sha256']
 images=[ELFFile(io.BytesIO(raw))]
rows=[]
for selected,async_switch,sdk_pending,back_during_drain in (
        (0,False,False,False),(1,False,False,False),(2,False,False,False),
        (2,True,False,False),(2,False,True,False),(2,False,True,True)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50000000,0x10000);u.mem_map(0x70000000,0x10000)
 for image in images:
  for s in image.iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
 get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 area=0x70000000;context=area+0x100;ui=area+0x1000;view=area+0x8000;done=area+0xff00
 put(ui+0x2b18+29*8,view)
 if firmware_sha:
  assert (get(0x405438),get(0x405304))==(int(wireless['entry'],16),int(wireless['initializer']['entry'],16))
 else:
  put(0x405438,symbols['xw_wireless_native_confirm']);put(0x405304,symbols['xw_wireless_native_init'])
 posts=[];requests=[];original=[];count=[2];nvp=[0 if async_switch else int(selected!=0)]
 def hook(cpu,pc,size,unused):
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
  if pc in (0x88494,0x88400):original.append(pc);return
  if pc==0xda84:
   requests.append(args[:2])
   if args[0]==2:
    assert args[1]==selected
    value=0x574d0001 if sdk_pending and len(requests)==1 else 0x574d0000
   elif args[0]==5:value=0x574e0000|selected
   elif args[0]==4:value=0x574dfffb if back_during_drain else 0x574d0000
   else:raise AssertionError(args)
  elif pc==0x37f5c:assert args[:2]==[6,0x600];u.mem_write(args[2],bytes(nvp))
  elif pc==0x38a18:assert args[:3]==[6,0x600,1];nvp[0]=1
  elif pc==0x3b374:value=1
  elif pc==0xb3300:value=2
  elif pc==0x2a984:value=ui
  elif pc==0x10a118:
   assert args[0]==view;u.mem_write(args[1],bytes(60));put(args[1]+52,count[0]);value=args[1]
  elif pc==0x10a0d4:assert args[0]==view;count[0]=get(args[1]+52)
  elif pc==0xa57f0:posts.append(args)
  elif pc==0x7461c:value=90
  elif pc==0x74608:value=0
  elif pc in (0x74668,0x17c42c,0x33b918,0x80050,0x8007c,0x4aca4):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,args,extra=0):
  sp=area+0xe000;put(sp,extra)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
  u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(address,done,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done
  return u.reg_read(UC_ARM_REG_R0)
 assert call(0x17c494,[context,193,0x3f55d8,154],2)==0
 put(0x4ee5d8,selected)
 assert call(0x17c608,[context,0x4a0119,0xff0000,0])==0
 if sdk_pending:
  assert list(u.mem_read(context,2))==[154,2]
  assert not posts and not original and get(0x4ee5d8)==selected
  assert requests==[[2,selected]]
  if back_during_drain:
   assert call(0x17c608,[context,0x4a0119,0xff0001,0])==0
   assert list(u.mem_read(context,2))==[90,1] and posts==[[0x20106,0,123,0]]
   assert requests==[[2,selected],[4,selected]] and not original
   assert call(0x17c608,[context,0x4a0116,0,0])==0
   assert list(u.mem_read(context,2))==[90,2]
   rows.append(dict(selected=selected,back_while_sdk_busy=True,final_state=[90,2],posts=posts))
   continue
  # The SDK's verified retirement is represented by the next successful reply.
  assert call(0x17c608,[context,0x4a0119,0xff0000,0])==0
 completion=None
 if async_switch:
  assert list(u.mem_read(context,2))==[154,4]
  assert posts==[[0x4c9007,0,0,0]] and nvp==[1]
  assert requests==[[2,selected]] and original==[0x88494]
  # These are the stock secondary Wi-Fi group's action bodies. Network
  # completion delivery remains a fixture, but Sony generates the UI event.
  event,_,value,arg=posts[-1]
  assert call(0x64504,[0,event,value,arg])==5
  assert posts[-1]==[0x2010e,0,113,0]
  assert call(0x646b4,[0,0x4c800f,0,0])==3
  assert posts[-1]==[0x4c0006,0,0,0]
  assert call(0x645a4,[0,0x4c800f,0,0])==1
  assert posts[-1]==[0x4a011c,0,90,0]
  event,_,completion,arg=posts[-1]
  assert call(0x17c608,[context,event,completion,arg])==0
  assert list(u.mem_read(context,2))==[90,1] and posts[-1]==[0x20106,0,123,0]
  assert requests==[[2,selected]]
  # The user can reopen Wireless Mode from the parent after completion.
  # Invoke that page's original entry state directly to check its refresh.
  assert call(0x17c494,[context,193,0x3f55d8,154],1)==0
 assert list(u.mem_read(context,2))==[154,1]
 assert requests==[[2,selected]]*(2 if sdk_pending else 1)+[[5,0]]
 assert original==[0x88494] and count[0]==3
 assert [p for p in posts if p[:3]==[0x20106,0,29]]==[[0x20106,0,29,selected]]
 assert posts[-1]==[0x20106,0,29,selected] and get(0x4ee5d8)==selected
 assert call(0x17c608,[context,0x4a0116,0,0])==0
 assert list(u.mem_read(context,2))==[154,2]
 assert call(0x17c608,[context,0x4a0119,0xff0001,0])==0
 assert list(u.mem_read(context,2))==[90,1] and posts[-1]==[0x20106,0,123,0]
 assert requests[-1]==[4,selected] and original==[0x88494]
 assert call(0x17c608,[context,0x4a0116,0,0])==0
 assert list(u.mem_read(context,2))==[90,2]
 rows.append(dict(selected=selected,sdk_pending_selection_preserved=sdk_pending,stock_completion_group=completion,posts=posts,final_state=[90,2],choice_count=count[0],single_selector_draw_request=True,back_while_sdk_busy=False))
report=dict(passed=True,cases=rows,firmware_sha256=firmware_sha,player_sha256=hashlib.sha256(raw).hexdigest(),device_accessed=False,firmware_created=False,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_wireless_mode_refresh.py']},
 limits=['Async case runs Sony completion actions and supplies the underlying power-service acknowledgements. Physical RF is unverified.',
         'Mode replies, NVP reads, widget properties, category leaves and ready-event delivery are fixtures; no physical rendering acceptance.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
