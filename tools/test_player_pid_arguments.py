"""Optional argument capture ABI, not a native prepare hook or installer."""
import hashlib
import io
import json
import struct
import subprocess
import time
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R7, UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from app_registry import ROOT
work=ROOT/'work/player-pid-arguments'/str(time.time_ns());work.mkdir(parents=True)
sources=['runtime/platform/player/host_pid.S','tools/fixtures/player_pid_arguments.c']
binary=work/'capture.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-DXW_PLAYER_CAPTURE_ARG2','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
elf=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
rows=[]
for ordinary in (True,False):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']!='PT_LOAD':continue
  a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
 area=0x71000000;u.mem_map(area,65536);stack=area+0xf000;done=area+0xff00;output=area+0x100
 args=(0xdead0001,0xbeef0001,0xcafe0001) if ordinary else (0x613e60,3,output)
 for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(register,value)
 u.reg_write(UC_ARM_REG_R3,0xbad00001)
 for register,value in ((UC_ARM_REG_R4,0x44444444),(UC_ARM_REG_R7,0x77777777),(UC_ARM_REG_R11,0xbbbbbbbb),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,done)):u.reg_write(register,value)
 u.mem_write(symbols['allow_output'],struct.pack('<I',not ordinary));u.mem_write(output,b'\x5a'*4)
 u.emu_start(symbols['getpid'],done,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==4321 and u.reg_read(UC_ARM_REG_SP)==stack
 assert tuple(u.reg_read(r) for r in (UC_ARM_REG_R4,UC_ARM_REG_R7,UC_ARM_REG_R11))==(0x44444444,0x77777777,0xbbbbbbbb)
 assert struct.unpack('<5I',u.mem_read(symbols['captured'],20))==(args[0],args[1],done,0x77777777,args[2])
 assert bytes(u.mem_read(output,4))==(b'\x5a'*4 if ordinary else struct.pack('<I',0x12345678))
 rows.append(dict(ordinary_getpid=ordinary,third_argument_preserved=True,stack_and_saved_registers_preserved=True,output_written=not ordinary))
report=dict(passed=True,device_accessed=False,optional_analysis_abi=True,cases=rows,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_player_pid_arguments.py']},
 limits=['Dispatcher is a test recorder; no original prepare function, image guard, native owner or lifecycle executes.','Default getpid assembly path is unchanged; this macro is not selected by current host builders.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
