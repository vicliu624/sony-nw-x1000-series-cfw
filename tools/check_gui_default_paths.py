"""Stock group0 directory initialization with virtual enumeration and libc services."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];base=0x70000000;u.mem_map(base,0x30000)
def readstr(p):
 b=bytearray()
 for i in range(1024):
  x=u.mem_read(p+i,1)[0]
  if not x:return bytes(b)
  b.append(x)
 raise AssertionError('unterminated')
def put(p,v):u.mem_write(p,struct.pack('<I',v))
dirs={};opened=[];available=True
u.mem_write(0x60014000,b'default\0')
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];answer=0
 if pc==0xf6728:uc.reg_write(UC_ARM_REG_PC,0x50000000);return
 if pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);answer=a[0]
 elif pc in (0x3387c0,0x1147b0,0x338e04):pass
 elif pc==0x338dd4:
  path=readstr(a[1]).decode();opened.append(path);dirs[a[0]]=False
  answer=0 if available or not path.startswith('/contents') else 7
 elif pc==0x338e1c:
  answer=0x551 if dirs[a[0]] else 0;dirs[a[0]]=True
 elif pc==0x338e8c:answer=0x60014000
 elif pc==0xdb08:answer=len(readstr(a[0]))
 elif pc==0xda0c:answer=int(readstr(a[0])!=readstr(a[1]))
 elif pc==0xd85c:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));answer=a[0]
 elif pc==0xe144:u.mem_write(a[0]+len(readstr(a[0])),readstr(a[1])[:a[2]]+b'\0');answer=a[0]
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[]
for available in (True,False):
 dirs.clear();opened.clear();n['call'](0xf6488,(base,0,0,0))
 roots=[readstr(base+offset).decode() for offset in (0xb61c,0x1881c)]
 assert roots[0]=='/usr/local/share/GUI/skinRom/common/default'
 assert roots[1]==('/contents/GUI/skin/common/default' if available else ''),roots
 rows.append({'external_directory_available_fixture':available,'opened':opened.copy(),'system_default_path':roots[0],'external_default_path':roots[1]})
r={'SpiderApp_sha256':n['digest'],'scope':'Nativef6488 group0 loop, stop before group1; enumeration/libc/filesystem init/record constructor virtual','cases':rows,'limits':['Supplied one default entry per available directory; no actual device/filesystem enumeration.','Proves separate stored paths, not override priority or actual loading.']}
Path(n['ROOT'],'sources/native-gui-default-paths.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
