"""Stock SID -> SWD load/parse -> STX lookup, with file and libc fixtures."""
from pathlib import Path
import io,json,hashlib,struct,re
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];area=ROOT/'work/home-feedback-resource-review-1';raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
swd=(area/'overlay/usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd').read_bytes();rows=[]
for stx in sorted((area/'overlay/usr/local/share/gemini/res/stx').glob('*.stx')):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x780000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x30000);u.mem_map(0x60000000,0x200000);sp=0x50028000;context=0x50002000;buffer=0x50004000
 u.mem_write(buffer,swd);u.mem_write(0x60000000,stx.read_bytes());u.mem_write(0x70b8dc+68,struct.pack('<II',0x60000000,0x60000000));events=[];measurements=[];heights=[];display_text=[]
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 u.mem_write(word(0xec448),struct.pack('<I',context))
 def string(a):
  b=bytearray()
  for n in range(9000):
   c=bytes(u.mem_read(a+n,1))
   if c==b'\0':return bytes(b)
   b.extend(c)
  raise AssertionError('unterminated')
 def hook(uc,pc,size,_):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
  if pc==0xd9a0:
   fmt=string(a[2]).decode();text=(fmt%(a[3],word(uc.reg_read(UC_ARM_REG_SP)))).encode();uc.mem_write(a[0],text+b'\0');result=len(text)
  elif pc==0xd574:uc.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
  elif pc==0xe09c:
   assert string(a[0])==b'/usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd' and a[1]==0
   events.append('open');result=7
  elif pc==0xe234:
   assert a[:2]==[3,7];uc.mem_write(a[2],bytes(88));uc.mem_write(a[2]+44,struct.pack('<I',len(swd)))
  elif pc==0xe324:assert a[0]==30;result=4096
  elif pc==0xd808:result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
  elif pc==0xdafc:
   assert a==[0,4096,1,1];events.append('map');result=buffer
  elif pc==0xd934:assert a==[buffer,4096,0,0] or a[:2]==[buffer,4096];events.append('unmap')
  elif pc==0xd6f4:assert a[0]==7;events.append('close')
  elif pc in (0xda0c,0xd6b8):
   left=string(a[0]);right=string(a[1])
   if pc==0xd6b8:left=left[:a[2]];right=right[:a[2]]
   result=(left>right)-(left<right)
  elif pc==0xd754:
   assert a[1]==0 and a[2]==10;m=re.match(rb'[+-]?\d+',string(a[0]));result=int(m.group()) if m else 0
  elif pc==0xf3ba8:
   assert a[:2]==[0x13ad1107,180]
   expected='Homebrew unavailable.\nCheck HOMEBREW folder.'.encode('utf-16le')+b'\0\0'
   assert bytes(uc.mem_read(a[2],len(expected)))==expected
   measurements.append({'font_id':hex(a[0]),'width':a[1]});result=2 # explicit metric-result fixture
  elif pc==0x10a448:heights.append(a[1])
  elif pc in (0xf56b4,0xf3af8,0xee9e4,0x10a938,0x10a9a4,0x10a24c):pass
  elif pc==0xf577c:
   assert a[3]==59;uc.mem_write(word(uc.reg_read(UC_ARM_REG_SP)+4),struct.pack('<I',0x50010000))
  elif pc==0xf3694:
   assert a[0]==0x50010000
   expected='Homebrew unavailable.\nCheck HOMEBREW folder.'.encode('utf-16le')+b'\0\0'
   assert bytes(uc.mem_read(a[1],len(expected)))==expected;display_text.append(True)
  else:return
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,99999);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50029000)
 u.emu_start(0x10a544,0x50029000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x50029000 and u.reg_read(UC_ARM_REG_SP)==sp
 pointer=u.reg_read(UC_ARM_REG_R0);text='Homebrew unavailable.\nCheck HOMEBREW folder.'.encode('utf-16le')+b'\0\0';assert bytes(u.mem_read(pointer,len(text)))==text
 assert events==['open','map','unmap','close']
 descriptor=0x5000e000;parent=0x50008000
 u.mem_write(descriptor,struct.pack('<12I',745,99999,1,0,0,0,0,0,0,0,0,2));u.mem_write(parent+0xaf4,struct.pack('<I',1))
 u.reg_write(UC_ARM_REG_R0,parent);u.reg_write(UC_ARM_REG_R1,descriptor);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50029000)
 u.emu_start(0x10ac20,0x50029000,count=1000000);assert u.reg_read(UC_ARM_REG_PC)==0x50029000 and u.reg_read(UC_ARM_REG_SP)==sp
 assert len(measurements)==1 and heights==[80] and display_text==[True]
 assert len(events)%4==0 and all(events[i:i+4]==['open','map','unmap','close'] for i in range(0,len(events),4))
 rows.append({'stx':stx.name,'events':events,'text_exact':True,'measurement_calls':measurements,'height_with_metric_fixture':heights[0]})
assert len(rows)==11
report={'passed':True,'stock_sid_file_loader_parser_and_lookup_executed':True,'cases':rows,'file_stat_mapping_libc_services_mocked':True,'stx_context_is_fixture':True,'font_measurement_call_verified':True,'actual_font_metrics_verified':False,'metric_result_fixture':2,'graphics_layout_helpers_mocked':True,'screen_render_verified':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(area/'resource-layout-report.json').write_text(json.dumps(report,indent=2)+'\n');print('11 stock resource/layout paths passed; font metric result remains a fixture')
