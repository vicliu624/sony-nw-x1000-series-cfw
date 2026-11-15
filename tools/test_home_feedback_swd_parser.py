"""Replay stock SWD parsing and Homebrew error lookup from a selected root."""
import argparse
from pathlib import Path
import io,json,hashlib,struct,tarfile,re
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from review_managed_root_capacity import read_root_input

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--localization-root', required=True, type=Path)
args = parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
stock_path = ROOT / 'work/upg-jp/verified-3.bin'
assert hashlib.sha256(stock_path.read_bytes()).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(stock_path, 'r:gz') as archive:
    stock = archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd').read()
path, localized, root_sha256 = read_root_input(args.localization_root, root_only=True)
with tarfile.open(fileobj=io.BytesIO(localized), mode='r:gz') as archive:
    new = archive.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd').read()
    wordings = {
        Path(member.name).name: archive.extractfile(member).read()
        for member in archive if member.isfile()
        and member.name.startswith('./usr/local/share/gemini/res/stx/') and member.name.endswith('.stx')
    }
rows=[]
english_text = 'Homebrew unavailable.\nCheck HOMEBREW.'
translated_text = {
    f'ucs2-dev-{code}.stx': json.loads(
        (ROOT / f'translations/x1000-{locale}.json').read_text(encoding='utf-8')
    )['translations']['7309']
    for code, locale in (('cs', 'zh-CN'), ('ct', 'zh-TW'))
}
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
  for stx, content in sorted(wordings.items()):
   assert len(content)<0x200000;u.mem_write(0x60000000,content)
   # Original ec864 returns this static resource object. Its header/mapping
   # fields are explicit initialized fixtures; lookup code itself is stock.
   u.mem_write(0x70b8dc+68,struct.pack('<II',0x60000000,0x60000000))
   u.reg_write(UC_ARM_REG_R0,context);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
   u.emu_start(0xec518,0x50019000,count=1000);assert u.reg_read(UC_ARM_REG_PC)==0x50019000
   pointer=u.reg_read(UC_ARM_REG_R0)
   expected_text=translated_text.get(stx, english_text).encode('utf-16le')+b'\0\0'
   assert bytes(u.mem_read(pointer,len(expected_text)))==expected_text
   linked.append(stx)
  assert len(linked)==11
 rows.append({'mapping':name,'tid0':tid,'count':count,'sha256':hashlib.sha256(data).hexdigest()})
report={'passed':True,'localization_root':path.relative_to(ROOT).as_posix(),'localization_root_sha256':root_sha256,'stock_tokenizer_and_line_parser_executed':True,'libc_compare_and_decimal_conversion_mocked':True,'cases':rows,'stx_text_lookup_verified':True,'linked_languages':linked,'stx_resource_context_is_fixture':True,'screen_render_verified':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
print(json.dumps(report,indent=2))
