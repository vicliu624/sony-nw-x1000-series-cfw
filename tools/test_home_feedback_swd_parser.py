"""Run stock SWD token/line parser on stock and new prototype mappings."""
from pathlib import Path
import io,json,hashlib,struct,tarfile,re
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:stock=archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd').read()
area=ROOT/'work/home-feedback-resource-review-1';new=(area/'overlay/usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd').read_bytes();rows=[]
for name,data,expected in [('stock',stock,27),('homebrew',new,7309)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x780000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x20000);context=0x50001000;buffer=0x50004000;sp=0x50018000
 u.mem_write(buffer,data);u.mem_write(context+12,struct.pack('<II',buffer,len(data)));u.mem_write(context+352,b'\xff'*400)
 def string(a):
  b=bytearray()
  for n in range(9000):
   c=bytes(u.mem_read(a+n,1))
   if c==b'\0':return bytes(b)
   b.extend(c)
  raise AssertionError('Unterminated')
 def hook(uc,pc,size,_):
  if pc in (0xda0c,0xd6b8):
   a=string(uc.reg_read(UC_ARM_REG_R0));b=string(uc.reg_read(UC_ARM_REG_R1))
   if pc==0xd6b8:n=uc.reg_read(UC_ARM_REG_R2);a=a[:n];b=b[:n]
   result=(a>b)-(a<b)
  elif pc==0xd754:
   assert uc.reg_read(UC_ARM_REG_R1)==0 and uc.reg_read(UC_ARM_REG_R2)==10
   m=re.match(rb'[+-]?\d+',string(uc.reg_read(UC_ARM_REG_R0)));result=int(m.group()) if m else 0
  else:return
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
 u.emu_start(0xebd58,0x50019000,count=100000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50019000 and u.reg_read(UC_ARM_REG_SP)==sp
 count=struct.unpack('<I',u.mem_read(context+344,4))[0];tid=struct.unpack('<I',u.mem_read(context+352,4))[0]
 assert count==1 and tid==expected,(name,count,tid)
 if name=='homebrew':
  u.mem_map(0x60000000,0x200000);linked=[]
  for stx in sorted((area/'overlay/usr/local/share/gemini/res/stx').glob('*.stx')):
   content=stx.read_bytes();assert len(content)<0x200000;u.mem_write(0x60000000,content)
   # Original ec864 returns this static resource object. Its header/mapping
   # fields are explicit initialized fixtures; lookup code itself is stock.
   u.mem_write(0x70b8dc+68,struct.pack('<II',0x60000000,0x60000000))
   u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
   u.emu_start(0xec518,0x50019000,count=1000);assert u.reg_read(UC_ARM_REG_PC)==0x50019000
   pointer=u.reg_read(UC_ARM_REG_R0);expected_text='Homebrew unavailable.\nCheck HOMEBREW folder.'.encode('utf-16le')+b'\0\0'
   assert bytes(u.mem_read(pointer,len(expected_text)))==expected_text
   linked.append(stx.name)
  assert len(linked)==11
 rows.append({'mapping':name,'tid0':tid,'count':count,'sha256':hashlib.sha256(data).hexdigest()})
report={'passed':True,'stock_tokenizer_and_line_parser_executed':True,'libc_compare_and_decimal_conversion_mocked':True,'cases':rows,'stx_text_lookup_verified':True,'linked_languages':linked,'stx_resource_context_is_fixture':True,'screen_render_verified':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'parser-linked-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
