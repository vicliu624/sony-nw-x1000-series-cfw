"""Original manager mode0/mode1 branch and notification construction, no IPC.
Target preparation and registry queries modeled; stop before state transition.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/sysmgrd').read_bytes()
digest=hashlib.sha256(raw).hexdigest();assert digest=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows=[]
for mode in (0,1):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x20000);core=0x2001000;changer=0x2007000;end=0x2000100;observer=0x2000200;events=[];phase='init'
 def put(a,n):u.mem_write(a,struct.pack('<I',n))
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def hook(uc,pc,size,unused):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
  if pc==end or (phase=='change' and pc==0x1485c):uc.emu_stop();return
  elif pc==observer:events.append({'recipient':a[1],'packet':list(struct.unpack('<3I',uc.mem_read(a[0],12)))})
  elif pc==0x110ac:result=0x2010000
  elif pc==0x115ec:put(a[2],1)  # modeled live application record
  elif pc==0x148bc:put(a[0]+8,a[1])  # bounded target preparation boundary
  elif pc in (0x1a458,0x1a4f0,0x1a508):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def reject(*args):raise AssertionError('Unexpected system instruction')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject)
 def call(pc,*args):
  for reg,val in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),list(args)+[0]*4):u.reg_write(reg,val)
  u.reg_write(UC_ARM_REG_SP,0x201f000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(pc,end,count=20000)
 call(0x14648,changer,core,0x211dc)
 assert u.reg_read(UC_ARM_REG_PC)==end and word(changer+0x4a0)==0xbd74
 call(0x14c84);put(changer,u.reg_read(UC_ARM_REG_R0));put(changer+4,1)
 put(core+0x51bc,observer);put(core+0x51c0,0x2011000)
 phase='change';call(0x1480c,changer,0x30001,0,mode)
 assert u.reg_read(UC_ARM_REG_PC)==0x1485c
 assert events==[{'recipient':1,'packet':[6 if mode==0 else 4,0,0]}]
 rows.append({'supplied_mode':mode,'original_callback_slot':hex(0x4a0 if mode==0 else 0x498),'notifications':events})
report={'passed':True,'sysmgrd_sha256':digest,'cases':rows,'physical_device_or_ipc':False,
 'limits':['Original constructor, mode branch, callback wrappers and notification framing execute.',
           'Initial active manager state/current app supplied; target preparation and registry state modeled.',
           'Stops before changer state transition; acknowledgements, process exit and target launch not executed.']}
(ROOT/'sources/stock-manager-switch-modes.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
