"""Original MG constructor ABI and a no-crypto PC model; no device access."""
import json,hashlib,struct,io,os,subprocess,tarfile,time
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/stock-mg-constructor'/str(time.time_ns());out.mkdir(parents=True)
archive=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(archive,'r:gz') as tar:raw=tar.extractfile('./lib/modules/mg.ko').read()
assert hashlib.sha256(raw).hexdigest()=='8831117d03cac26f238b0c720cb78c2097d2591542fe28b4795cc1970ec5bfba'
(out/'mg.ko').write_bytes(raw)
e=ELFFile(io.BytesIO(raw));symbols=e.get_section_by_name('.symtab');md={s.name:s for s in symbols.iter_symbols()}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);base=0x30000000;u.mem_map(base,0x400000);u.mem_map(0x50000000,0x200000);u.mem_map(0x70000000,0x10000);sections={};cursor=base
for n,s in enumerate(e.iter_sections()):
 if s['sh_flags']&2 and s['sh_size']:
  cursor=(cursor+4095)&~4095;sections[n]=cursor
  if s['sh_type']!='SHT_NOBITS':u.mem_write(cursor,s.data())
  cursor+=s['sh_size']
external={}
def symbol(s):
 if s['st_shndx']=='SHN_UNDEF':
  if not s.name:return 0
  if s.name not in external:external[s.name]=0x30300000+len(external)*4
  return external[s.name]
 if s['st_shndx']=='SHN_ABS':return s['st_value']
 return sections[s['st_shndx']]+s['st_value']
for s in e.iter_sections():
 if s['sh_type']!='SHT_REL' or s['sh_info'] not in sections:continue
 for r in s.iter_relocations():
  p=sections[s['sh_info']]+r['r_offset'];old=struct.unpack('<I',u.mem_read(p,4))[0];target=symbol(symbols.get_symbol(r['r_info_sym']));kind=r['r_info_type']
  if kind==2:value=old+target
  elif kind==3:value=old+target-p
  elif kind in (1,28,29):
   a=(old&0xffffff)<<2
   if a&0x2000000:a-=0x4000000
   delta=target+a-p;assert not delta&3 and -(1<<25)<=delta<(1<<25);value=(old&0xff000000)|((delta>>2)&0xffffff)
  elif kind==40:continue
  else:raise AssertionError(kind)
  u.mem_write(p,struct.pack('<I',value&0xffffffff))
reg=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3);trace=[];failure=0;alloc=0x50100000;remap_failure=0
hooked={v:k for k,v in external.items()}
def hook(cpu,pc,size,unused):
 global alloc
 args=[cpu.reg_read(r) for r in reg]
 if pc==symbol(md['ddmgInitialize']):trace.append(dict(call='ddmgInitialize-hardware-boundary',result=failure));cpu.reg_write(UC_ARM_REG_R0,failure&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
 if pc not in hooked:return
 name=hooked[pc];value=0;trace.append(dict(call=name,args=args))
 if name=='__memzero':cpu.mem_write(args[0],bytes(args[1]))
 elif name=='__kmalloc':value=alloc;alloc+=(args[0]+4095)&~4095
 elif name=='remap_pfn_range':value=remap_failure&0xffffffff
 elif name not in ('printk','kfree'):raise AssertionError(name)
 cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(name,*args):
 for r,v in zip(reg,list(args)+[0]*4):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,0x500f0000);u.reg_write(UC_ARM_REG_LR,0x7000ff00);u.emu_start(symbol(md[name]),0x7000ff00,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x7000ff00,(hex(u.reg_read(UC_ARM_REG_PC)),trace[-20:]);return u.reg_read(UC_ARM_REG_R0)
rows=[]
mapping_rows=[]
for remap_failure in (0,-19):
 trace.clear();assert call('MgipOpen',0,0)==0
 vma=0x50002000;u.mem_write(vma,struct.pack('<5I',0,0x50010000,0x50011000,0,3))
 result=call('MgipMmap',0,vma)
 assert result==(0 if not remap_failure else 0xffffffff)
 remaps=[r for r in trace if r['call']=='remap_pfn_range'];assert len(remaps)==1 and remaps[0]['args'][1]==0x50010000 and remaps[0]['args'][3]==4096
 mapping_rows.append(dict(kernel_remap_result=remap_failure,mmap_return=result,kernel_calls=list(trace)))
for failure in (0,-19):
 trace.clear();opened=call('MgipOpen',0,0)
 arg=0x50001000;request=struct.pack('<I',0x200)+bytes(36);u.mem_write(arg,request)
 result=call('MgipIoctl',0,0,0x89a0,arg)
 assert opened==0 and result==0 and bytes(u.mem_read(arg,40))==request
 assert [r['args'][1] for r in trace if r['call']=='__memzero']==[56,24,8,40,16,8,12,8,8,16]
 rows.append(dict(hardware_initializer_result=failure,open_return=opened,ioctl_return=result,request_unchanged=bytes(u.mem_read(arg,40))==request,trace=list(trace)))
sources=['tools/fixtures/stock_mg_constructor_test.c'];flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-variable']
host=out/'model.host';subprocess.run(['gcc',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=10);(out/'host.log').write_text(run.stdout+run.stderr)
assert 'STOCK_MG_CONSTRUCTOR_MODEL_PASS' in run.stdout
libs=stock_libraries();arm=out/'model.arm';startup=['runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv',*sources,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,check=True,timeout=10)
(out/'arm.log').write_text(run.stdout+run.stderr);assert 'STOCK_MG_CONSTRUCTOR_MODEL_PASS' in run.stdout
report=dict(passed=True,host_sanitizers=True,sony_libc_arm926=True,module_sha256=hashlib.sha256(raw).hexdigest(),original_relocated_driver_executed=True,physical_device_access=False,hardware_initialization_stubbed=True,rows=rows,mapping_rows=mapping_rows,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*startup,'tools/fixtures/stock_mg_constructor_model.h','tools/test_stock_mg_constructor.py']},
 limits=['Hardware initializer is stubbed at its original function entry; authentication and crypto are not emulated.',
 'Original ioctl constructor completion and empty handle initialization execute, not a complete Sony startup or APF return.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
