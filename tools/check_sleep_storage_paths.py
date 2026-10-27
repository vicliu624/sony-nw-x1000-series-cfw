"""Replay pinned Sony sleep/storage branches. PC Unicorn only; no player I/O."""
from pathlib import Path
import io,struct,json,hashlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/sysmgrd').read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
e=ELFFile(io.BytesIO(b));syms={s.name:s['st_value']for s in e.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for kind,parameter in [('sleep',0),('sleep',2),('sleep-usb',2),('sleep-write-error',0),('awake',0x100),('awake',0x800),('unmount',1),('unmount',3),('unmount',4),('unmount',5)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000);u.mem_map(0x60000000,0x20000)
 for seg in e.iter_segments():
  if seg['p_type']=='PT_LOAD':u.mem_write(seg['p_vaddr'],seg.data())
 core=0x60000000;sp=0x6001f000;stop=0x6001fff0;events=[];seen=[]
 def put(p,n):u.mem_write(p,struct.pack('<I',n))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 def cstr(p):
  out=bytearray()
  for i in range(512):
   x=bytes(u.mem_read(p+i,1))
   if x==b'\0':return out.decode()
   out+=x
  raise AssertionError('string')
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]];ret=0
  if pc in [0x12b40,0x12e84,0x129d0,0x17894,0x17950]:seen.append(hex(pc));return
  if pc==0xa188:ret=1
  elif pc in [0x1c4d0,0x1c5ac,0x1e518]:pass
  elif kind.startswith('sleep') and pc in [0xa780,0xa714,0xa6ac]:events.append(['policy-fixture',hex(pc)]);ret=1 if kind=='sleep-usb' and pc in [0xa714,0xa6ac] else 0
  elif kind.startswith('sleep') and pc==0xa81c:events.append(['timer-fixture',hex(pc)]);ret=0
  elif pc==0x17588:ret=1
  elif pc==syms['open']:events.append(['open',cstr(a[0]),a[1]]);ret=42
  elif pc==syms['write']:
   events.append(['write',a[0],bytes(uc.mem_read(a[1],a[2])).decode()]);ret=-1 if kind=='sleep-write-error' else a[2]
   if kind=='sleep-write-error':events.append(['injected-write-result',-1,'errno=EAGAIN'])
  elif pc==syms['close']:events.append(['close',a[0]])
  elif pc==syms['ioctl']:events.append(['ioctl',a[0],hex(a[1])]);put(a[2],parameter)
  elif pc==syms['sync']:events.append(['sync'])
  elif pc==syms['umount']:events.append(['umount',cstr(a[0])])
  elif pc in [0x1c888,0x1c8c8]:raise AssertionError(('unexpected exception',kind,parameter,hex(pc)))
  else:return
  uc.reg_write(UC_ARM_REG_R0,ret&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 # Run full original functions except declared imported/policy boundaries.
 u.hook_add(UC_HOOK_CODE,hook)
 if kind.startswith('sleep'):entry=0xaaac;put(core+0x503c,3);put(core+0x5164,parameter);args=[core]
 elif kind=='awake':entry=0x17950;args=[42]
 else:entry=0xe084;put(core+0x503c,parameter);args=[core]
 for reg,n in zip([UC_ARM_REG_R0,UC_ARM_REG_R1],args):u.reg_write(reg,n)
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop);u.emu_start(entry,stop,count=500000);assert u.reg_read(UC_ARM_REG_PC)==stop
 result=u.reg_read(UC_ARM_REG_R0)
 if kind.startswith('sleep'):
  assert ['open','/proc/pm',1]in events
  assert ['write',42,'S4' if kind=='sleep-usb' else 'S3']in events,(kind,parameter,events)
  assert not any(x[0]=='umount'for x in events)
  assert word(core+0x503c)==4 and result==0
 elif kind=='awake':assert result==parameter and not any(x[0]=='umount'for x in events)
 elif parameter in [1,3]:assert ['umount','/contents']in events and result==0
 else:assert not any(x[0]=='umount'for x in events)and result==0x1d03
 rows.append({'kind':kind,'fixture':parameter,'entry':hex(entry),'return':hex(result),'native_helpers':seen,'events':events})
r={'all_passed':True,'sysmgrd_sha256':sha,'physical_device_access':False,'cases':rows,'scope':'Original aaac/129d0/17894 and17950 plus e084/12e84/12b40 execute. Sleep enters supplied core state3 with prepare acknowledgments already complete; mode/policy/timer, libc and physical power virtual. No whole boot, application sleep callbacks, actual suspend or hardware fault reproduction.'}
out=ROOT/'work/external-language-bridge-8-ram-snapshot/sleep-storage-replay.json';out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
