"""Original exit actions through optional PID capture and fallback bridge.

Maps a separate scratch page in Unicorn, never edits an on-disk Sony image.
"""
import hashlib,io,json,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R4,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from player_prepare_bridge import prepare_bridge,PREPARE_BRIDGE,PREPARE_HANDLED
from build_player_met_anchor import branch
work=ROOT/'work/player-prepare-bridge'/str(time.time_ns());work.mkdir(parents=True)
sources=['runtime/platform/player/host_pid.S','tools/fixtures/player_pid_arguments.c']
binary=work/'capture.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-DXW_PLAYER_CAPTURE_ARG2','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
rows=[]
for action in (0x718c0,0x71a3c):
 for result in (4321,0xffffffff,PREPARE_HANDLED):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  for elf in (ELFFile(io.BytesIO(stock)),helper):
   for s in elf.iter_segments():
    if s['p_type']!='PT_LOAD':continue
    a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  u.mem_map(0x4d7000,4096);u.mem_write(PREPARE_BRIDGE,prepare_bridge())
  area=0x71000000;u.mem_map(area,65536);stack=area+0xf000;done=area+0xff00;native=[]
  put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
  get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
  site=0x718e0 if action==0x718c0 else 0x71aa4
  assert get(site)==branch(site,0x112fc,True)
  put(site,branch(site,PREPARE_BRIDGE,True));put(symbols['dispatch_result'],result)
  def hook(cpu,pc,size,context):
   if pc==0xda84:cpu.reg_write(UC_ARM_REG_PC,symbols['getpid']);return
   value=0
   if pc==0x112fc:
    args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    assert args[:2]==[0x613e60,3] and get(args[2])==0
    native.append(args);put(args[2],77)
   elif pc not in (0xe5f4,0xf680):return
   cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in ((UC_ARM_REG_R0,area),(UC_ARM_REG_R4,0x44444444),(UC_ARM_REG_R7,0x77777777),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,done)):u.reg_write(r,v)
  u.emu_start(action,done,count=100000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0 and u.reg_read(UC_ARM_REG_SP)==stack
  assert u.reg_read(UC_ARM_REG_R4)==0x44444444 and u.reg_read(UC_ARM_REG_R7)==0x77777777
  captured=struct.unpack('<5I',u.mem_read(symbols['captured'],20))
  assert captured[:4]==(0x613e60,3,PREPARE_BRIDGE+8,0x77777777) and get(symbols['calls'])==1
  assert len(native)==int(result!=PREPARE_HANDLED)
  assert get(captured[4])==(0 if result==PREPARE_HANDLED else 77)
  if native:assert captured[4]==native[0][2]
  rows.append(dict(action=hex(action),dispatcher_result=hex(result),native_fallback_calls=len(native),third_argument_preserved=True,stack_restored=True))
report=dict(passed=True,device_accessed=False,firmware_created=False,on_disk_sony_image_modified=False,cases=rows,
 stock_sha256=hashlib.sha256(stock).hexdigest(),test_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),bridge_bytes=len(prepare_bridge()),bridge_sha256=hashlib.sha256(prepare_bridge()).hexdigest(),
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/player_prepare_bridge.py','tools/test_player_prepare_bridge.py','tools/build_player_met_anchor.py']},
 limits=['Original exit action/getter, bridge and capture shim execute; dispatcher, gate conditions and original prepare body are models.',
         'Scratch stub page is mapped only in Unicorn. No ELF slot/capacity/composition/loader, image/owner/context guard or actual deferred service is qualified.',
         'Non-marker inputs model no owned SDK resources. With active/faulted resources a future dispatcher must suppress native cleanup; that policy is not implemented by this test.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
