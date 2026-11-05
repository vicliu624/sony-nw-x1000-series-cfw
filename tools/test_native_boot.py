"""Read-only boot qualification fixtures plus original cached-setting getter."""
import hashlib,io,json,struct,subprocess,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/native-boot'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/wireless/native_boot.c','runtime/platform/wireless/radio_modules.c','tools/test_native_boot.c']
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DXW_NATIVE_BOOT_FIXTURE']
host=out/'test.host'
subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=10);assert result.returncode==0,result.stdout+result.stderr
libs=stock_libraries();arm=out/'test.arm';init=out/'init.arm';startup=['runtime/store/start.c','runtime/store/start.S']
armflags=[*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none']
links=[str(libs[n]) for n in ('libc.so.6','ld-linux.so.3')]
subprocess.run(['arm-linux-gnueabi-gcc',*armflags,*sources,*startup,*links,'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
init_source='tools/fixtures/player_worker_system_init.c'
subprocess.run(['arm-linux-gnueabi-gcc',*armflags,init_source,*startup,*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
guest=run_guest(out,init,{'test':arm},libs,['NATIVE_BOOT_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
assert guest['passed'],(out/'serial.log').read_text(errors='replace')[-1800:]
# Execute the production C flag reader and actual original byte getter together.
getter=out/'getter.elf'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-ffunction-sections','-fdata-sections','-march=armv5te','-marm','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--gc-sections,--build-id=none,-Ttext=0x51000000,-e,xw_native_boot_flag',sources[0],'-o',str(getter)],cwd=ROOT,check=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50ff0000,0x40000);u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
for data in (raw,getter.read_bytes()):
 for segment in ELFFile(io.BytesIO(data)).iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
cache=struct.unpack('<I',u.mem_read(0x383e4,4))[0];cases=[]
for flag in (0,1,2,255):
 u.mem_write(cache,bytes([flag]));u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(ELFFile(io.BytesIO(getter.read_bytes()))['e_entry'],0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 result=u.reg_read(UC_ARM_REG_R0);assert result==(flag if flag<2 else 0xffffffff)
 assert u.mem_read(cache,1)[0]==flag;cases.append(dict(cached=flag,result=result))
report=dict(passed=True,device_accessed=False,firmware_created=False,host_sanitizers=True,original_libc_arm=True,
 qualification_matrix_cases=128,original_cached_getter_cases=cases,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/wireless/native_boot.h','runtime/platform/wireless/radio_modules.h','tools/test_native_boot.py',init_source,*startup]},
 limits=['Manager status, modules text, entropy and I/O errors are fixtures; no physical off/driver or random-device qualification.',
 'The production C getter and original ARM cached-property byte read execute; persistent configuration is not written.',
 'No device, flash package or complete native boot scheduling/ownership qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
