"""Observe stock renderer initialization up to unsupported services, PC only."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UcError
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'work/home-feedback-font-init-probe-7';out.mkdir(exist_ok=False);raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';elf=ELFFile(io.BytesIO(raw));names={s['st_value']:s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_value']}
plt=elf.get_section_by_name('.plt');u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,0x20000);u.mem_map(0x60000000,0x1000000);sp=0x50018000;path=0x50001000;u.mem_write(path,b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf\0');import tarfile
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as tar:font=tar.extractfile('./usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf').read()
u.mem_map(0x61000000,(len(font)+4095)&~4095);u.mem_write(0x61000000,font);position=[0]
events=[];stop=[];heap=[0x60000000]
def string(a):
 b=bytearray()
 for n in range(4096):
  c=bytes(u.mem_read(a+n,1))
  if c==b'\0':return bytes(b)
  b.extend(c)
 raise AssertionError('Unterminated')
def hook(uc,pc,size,_):
 if not plt['sh_addr']<=pc<plt['sh_addr']+plt['sh_size']:return
 name=names.get(pc,'UNKNOWN_PLT');a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];events.append({'pc':hex(pc),'service':name,'args':a});result=0
 if name=='memset':uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
 elif name in ('memcpy','memmove'):uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
 elif name=='strlen':result=len(string(a[0]))
 elif name=='strncpy':
  text=string(a[1])[:a[2]];uc.mem_write(a[0],text+bytes(a[2]-len(text)));result=a[0]
 elif name=='strcpy':uc.mem_write(a[0],string(a[1])+b'\0');result=a[0]
 elif name=='strncmp':
  left=string(a[0])[:a[2]];right=string(a[1])[:a[2]];result=(left>right)-(left<right)
 elif name=='memcmp':
  left=bytes(uc.mem_read(a[0],a[2]));right=bytes(uc.mem_read(a[1],a[2]));result=(left>right)-(left<right)
 elif name=='strcmp':left=string(a[0]);right=string(a[1]);result=(left>right)-(left<right)
 elif name in ('malloc','calloc'):
  n=a[0] if name=='malloc' else a[0]*a[1];assert 0<n<0x1000000 and heap[0]+n<=0x61000000;result=heap[0];heap[0]+=(n+7)&~7
 elif name=='free':pass
 elif name=='open':
  assert string(a[0])==b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf' and a[1]==0;position[0]=0;result=7
 elif name=='read':
  assert a[0]==7;chunk=font[position[0]:position[0]+a[2]];position[0]+=len(chunk)
  if chunk:uc.mem_write(a[1],chunk)
  result=len(chunk)
 elif name=='__fxstat':
  assert a[:2]==[3,7];uc.mem_write(a[2],bytes(88));uc.mem_write(a[2]+44,len(font).to_bytes(4,'little'))
 elif name=='sysconf':assert a[0]==30;result=4096
 elif name=='__aeabi_uidivmod':result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
 elif name=='mmap':
  assert a[2]==1 and a[3]==1;result=0x61000000
 elif name in ('close','munmap'):pass
 else:stop.append({'reason':'unsupported service','pc':hex(pc),'service':name});uc.emu_stop();return
 uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,path);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
try:u.emu_start(0x129d84,0x50019000,count=200000)
except (UcError,AssertionError) as error:stop.append({'reason':type(error).__name__,'text':str(error),'pc':hex(u.reg_read(UC_ARM_REG_PC))})
init_return=u.reg_read(UC_ARM_REG_R0);measurements=[]
if not stop and u.reg_read(UC_ARM_REG_PC)==0x50019000 and init_return==0:
 for text in ('','iiii','WWWW','Homebrew unavailable.','Check HOMEBREW folder.','Homebrew unavailable.\nCheck HOMEBREW folder.','Homebrew unavailable.\nCheck HOMEBREW.','App unavailable.\nCheck app files.'):
  pointer=0x50004000;u.mem_write(pointer,text.encode('utf-16le')+b'\0\0')
  for function,label in ((0xf3c34,'height'),(0xf3ba8,'lines')):
   u.reg_write(UC_ARM_REG_R0,0x13ad1107);u.reg_write(UC_ARM_REG_R1,180);u.reg_write(UC_ARM_REG_R2,pointer);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
   try:u.emu_start(function,0x50019000,count=1000000)
   except UcError as error:stop.append({'reason':'metric '+str(error),'pc':hex(u.reg_read(UC_ARM_REG_PC))})
   measurements.append({'text':text,'kind':label,'result':u.reg_read(UC_ARM_REG_R0),'layout_bounds':struct.unpack('<8I',u.mem_read(0x70c610 if function==0xf3c34 else 0x70c5f0,32)),'returned':u.reg_read(UC_ARM_REG_PC)==0x50019000})
by_case={(m['text'],m['kind']):m for m in measurements}
passed=not stop and init_return==0 and all(m['returned'] for m in measurements) and by_case.get(('Homebrew unavailable.\nCheck HOMEBREW.','lines'),{}).get('result')==2
j={'passed':passed,'stock_sha256':hashlib.sha256(raw).hexdigest(),'font_sha256':hashlib.sha256(font).hexdigest(),'metric_functions_not_interposed':True,'scope':'Stock renderer initialization and metric observation with original LCF; libc/file/heap interfaces are fixtures','initialization_return':init_return,'events':events,'stop':stop,'measurements':measurements,'hardware_tested':False,'candidate4_changed':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'report.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({'initialization_return':init_return,'stop':stop,'measurements':measurements},indent=2))
