"""Original SpiderApp stop/close helper; all device operations are virtual."""
from pathlib import Path
import hashlib,io,json,struct,itertools
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R5,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for route,(opened,streaming,result) in itertools.product(('direct','table','native-dispatch'),((0,0,0),(1,0,0),(1,1,0),(1,1,-1))):
 via_table=route!='direct'
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segs=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 low=min(s['p_vaddr'] for s in segs)&~4095;high=(max(s['p_vaddr']+s['p_memsz'] for s in segs)+4095)&~4095
 u.mem_map(low,high-low)
 for s in segs:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x60000000,0x20000);obj=0x60001000
 u.mem_write(obj+0xf49,bytes([opened]));u.mem_write(obj+0xf78,bytes([streaming]))
 u.mem_write(0x806efc,struct.pack('<I',17));calls=[]
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if pc==symbols['ioctl']:
   assert a[:2]==[17,0x40045613] and struct.unpack('<I',uc.mem_read(a[2],4))[0]==1
   calls.append({'call':'ioctl','request':'0x40045613','type_word':1,'virtual_result':result});ret=result
  elif pc==symbols['close']:
   assert a[0]==17;calls.append({'call':'close','fd':17});ret=0
  elif pc==0x23c3e4:calls.append({'call':'diagnostic'});ret=0
  else:return
  uc.reg_write(UC_ARM_REG_R0,ret&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 entry=0x236b5c
 if via_table:
  # Only the constructor's original vtable-assignment prefix, not full object init.
  u.reg_write(UC_ARM_REG_R5,obj)
  u.emu_start(0x234314,0x234320,count=20)
  table=struct.unpack('<I',u.mem_read(obj,4))[0]
  assert table==0x4833b8
  entry=struct.unpack('<I',u.mem_read(table+0x7c,4))[0]
  assert entry==0x236be8
 u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x6001f000)
 if route=='native-dispatch':
  entry=0x1ff87c;u.reg_write(UC_ARM_REG_R1,obj)
 u.emu_start(entry,0x6001f000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x6001f000
 expected=['ioctl','diagnostic'] if result else ['ioctl','close'] if streaming else ['close'] if opened else []
 assert [c['call'] for c in calls]==expected
 assert u.reg_read(UC_ARM_REG_R0)==(0xffffffff if result else 0)
 assert u.mem_read(obj+0xf49,1)==bytes([opened if result else 0])
 assert u.mem_read(obj+0xf78,1)==bytes([streaming if result else 0])
 rows.append({'route':route,'entry':hex(entry),'via_native_constructor_table_prefix':via_table,'opened_fixture':opened,'streaming_fixture':streaming,'calls':calls,'return_signed':-1 if result else 0})
report={'input_sha256':digest,'entry':'0x236b5c','cases':rows,'finding':'Active stream sends STREAMOFF type1, then closes on success. Failed ioctl logs and returns-1 without close or clearing flags.',
        'limits':['Object flags and fd supplied; ioctl/close/logging virtual. Actual device identity and normal lifecycle caller not yet proven.',
                  'Table cases execute only constructor vtable assignment. Native-dispatch cases execute original1ff87c virtual-call wrapper with supplied object in r1; real owner passing this object and full construction remain unproven.',
                  'Type1 is observed userland payload, distinct from earlier type2 kernel fixture; no claim those fixtures are equivalent. No real usercopy, kernel integration or hardware.']}
(ROOT/'sources/native-spider-video-stop.json').write_text(json.dumps(report,indent=2)+'\n')
print('Twelve original SpiderApp stop/close cases passed; direct/table/native virtual dispatch, supplied object, STREAMOFF type1')
