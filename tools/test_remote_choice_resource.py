"""Original SID filename/load/parser/STX path for Remote title and On/Off."""
import argparse,hashlib,io,json,re,struct,tarfile,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from prepare_managed_firmware_review import unpack
from remote_choice_resource import TARGET
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True)
parser.add_argument('--firmware',help='Check resource and wording bytes from this exact UPG')
args=parser.parse_args()
rp,review=receipt(args.review);swd_path=private(review['artifact']);assert digest(swd_path)==review['sha256']
swd=swd_path.read_bytes();raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
firmware_sha=None
wording={}
if args.firmware:
 firmware=private(args.firmware);data=firmware.read_bytes()
 firmware_sha=hashlib.sha256(data).hexdigest()
 _,parts=unpack(data,require_stock=False)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
  item=archive.getmember('./'+TARGET)
  assert item.isfile() and (item.mode,item.uid,item.gid)==(review['mode'],review['uid'],review['gid'])
  assert archive.extractfile(item).read()==swd
  for language,entry in review['languages'].items():
   relative=entry['path'].split('/root-overlay/',1)[1]
   wording[language]=archive.extractfile('./'+relative).read()
rows=[]
for language,entry in review['languages'].items():
 stx=wording[language] if args.firmware else private(entry['path']).read_bytes()
 assert hashlib.sha256(stx).hexdigest()==entry['sha256']
 for local,key in ((0,'on'),(1,'off'),(0x400,'title')):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50000000,0x30000);u.mem_map(0x60000000,0x200000)
  for s in ELFFile(io.BytesIO(raw)).iter_segments():
   if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
  context=0x50002000;buffer=0x50004000;sp=0x50028000;done=0x50029000
  put=lambda a,v:u.mem_write(a,struct.pack('<I',v))
  word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
  u.mem_write(buffer,swd);u.mem_write(0x60000000,stx);u.mem_write(0x70b8dc+68,struct.pack('<II',0x60000000,0x60000000))
  put(word(0xec448),context);events=[]
  def string(address):
   result=bytearray()
   for i in range(9000):
    c=bytes(u.mem_read(address+i,1))
    if c==b'\0':return bytes(result)
    result.extend(c)
   raise AssertionError('Unterminated string')
  def hook(cpu,pc,size,unused):
   a=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
   if pc==0xd9a0:
    text=(string(a[2]).decode()%(a[3],word(cpu.reg_read(UC_ARM_REG_SP)))).encode();u.mem_write(a[0],text+b'\0');value=len(text)
   elif pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);value=a[0]
   elif pc==0xe09c:
    assert string(a[0])==b'/usr/local/share/gemini/res/swd/ucs2-dev-sid-139-01.swd' and a[1]==0
    events.append('open');value=7
   elif pc==0xe234:
    assert a[:2]==[3,7];u.mem_write(a[2],bytes(88));put(a[2]+44,len(swd))
   elif pc==0xe324:assert a[0]==30;value=4096
   elif pc==0xd808:value=a[0]//a[1];cpu.reg_write(UC_ARM_REG_R1,a[0]%a[1])
   elif pc==0xdafc:assert a==[0,4096,1,1];events.append('map');value=buffer
   elif pc==0xd934:assert a[:2]==[buffer,4096];events.append('unmap')
   elif pc==0xd6f4:assert a[0]==7;events.append('close')
   elif pc in (0xda0c,0xd6b8):
    left,right=string(a[0]),string(a[1])
    if pc==0xd6b8:left,right=left[:a[2]],right[:a[2]]
    value=(left>right)-(left<right)
   elif pc==0xd754:
    assert a[1:3]==[0,10];m=re.match(rb'[+-]?\d+',string(a[0]));value=int(m.group()) if m else 0
   else:return
   cpu.reg_write(UC_ARM_REG_R0,value&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in ((UC_ARM_REG_R0,13901),(UC_ARM_REG_R1,local),(UC_ARM_REG_SP,sp),(UC_ARM_REG_LR,done)):u.reg_write(r,v)
  u.emu_start(0x10a544,done,count=200000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_SP)==sp
  expected=entry[key].encode('utf-16le')+b'\0\0'
  assert bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0),len(expected)))==expected
  assert events==['open','map','unmap','close']
  rows.append(dict(language=language,field=key,text_exact=True,events=events))
assert len(rows)==33
report=dict(passed=True,resource_sha256=review['sha256'],firmware_sha256=firmware_sha,cases=rows,
 original_sid_filename_loader_parser_and_stx_lookup=True,device_accessed=False,firmware_created=False,
 source_hashes={'tools/test_remote_choice_resource.py':digest(ROOT/'tools/test_remote_choice_resource.py')},
 limits=['File/stat/mapping and libc operations are fixtures; STX resource context is supplied.',
         'No font drawing, active view ownership, physical display or firmware installation.'])
out=ROOT/'work/remote-choice-resource-check'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
