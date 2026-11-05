"""Execute software admission C + stock singleton getters; no USB authority claim."""
import hashlib,io,json,struct,subprocess,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/player-remote-ready'/str(time.time_ns());out.mkdir(parents=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
sources=['runtime/platform/player/remote_ready.c','tools/fixtures/player_remote_ready.c'];binary=out/'ready.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()};rows=[]
for case in ('ready','off','wifi','bad-image','inactive','busy-cache','sleep-prepare','manager-request19','exit','handoff','usb-prepare','bad-command','wrong-tracker','pending','same-device','bad-directory','stat-failure','transition','aux-transition'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for elf in (ELFFile(io.BytesIO(raw)),helper) for s in elf.iter_segments() if s['p_type']=='PT_LOAD'];merged=[]
 for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x71000000,65536);done=0x7100ff00
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 for a,v in ((0x613e64,7),(0x613e68,0),(0x613eac,1),(0x613e8c,0x66efe8),(0x66efe8,0),(0x820f6c,2),(0x613e30,0)):put(a,v)
 changes={'off':('test_mode',0),'wifi':('test_mode',1),'bad-image':('test_image',0),'same-device':('test_same_device',1),'bad-directory':('test_bad_directory',1),'stat-failure':('test_stat_failure',1),'transition':('test_transition',1),'aux-transition':('test_transition',2)}
 if case in changes:name,value=changes[case];put(symbols[name],value)
 for name,a,value in (('inactive',0x820f6c,1),('busy-cache',0x613e30,2),('sleep-prepare',0x613e64,1),('manager-request19',0x613e64,11),('exit',0x613e64,3),('handoff',0x613e64,6),('usb-prepare',0x613e64,8),('bad-command',0x613e64,22),('wrong-tracker',0x613e8c,0),('pending',0x66efe8,1)):
  if case==name:put(a,value)
 u.reg_write(UC_ARM_REG_SP,0x7100f000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(symbols['xw_player_remote_software_ready'],done,count=200000);assert u.reg_read(UC_ARM_REG_PC)==done
 result=u.reg_read(UC_ARM_REG_R0);assert result==int(case=='ready'),case
 if case in ('ready','busy-cache','inactive','sleep-prepare','manager-request19','handoff','exit','usb-prepare'):
  calls=struct.unpack('<I',u.mem_read(symbols['test_stat_calls'],4))[0]
  u.reg_write(UC_ARM_REG_SP,0x7100f000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(symbols['xw_player_remote_state_active'],done,count=200000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==int(case=='ready')
  assert struct.unpack('<I',u.mem_read(symbols['test_stat_calls'],4))[0]==calls
 rows.append(dict(case=case,admitted=bool(result)))
print(json.dumps(dict(passed=True,device_accessed=False,cases=rows,filesystem_modeled=True,mode_authority_and_image_gate_modeled=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/player/remote_ready.h','tools/test_player_remote_ready.py']},limits=['Original getters and C sampling execute; filesystem/image/mode qualification is fixture supplied.','No independent physical USB authority proof, native callback timing or installed remote factory.']),indent=2))
