"""Stock SID -> SWD load/parse -> STX lookup, with file and libc fixtures."""
from pathlib import Path
import io,json,hashlib,struct,re
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];area=ROOT/'work/home-feedback-resource-review-2';elf_build=json.loads((ROOT/'work/home-feedback-resource-elf-review-1/build.json').read_text());raw=(ROOT/'work/home-feedback-resource-elf-review-1/SpiderApp.resource.analysis-only.elf').read_bytes();assert hashlib.sha256(raw).hexdigest()==elf_build['candidate_sha256']
import tarfile
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:font=archive.extractfile('./usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf').read()
swd=(area/'overlay/usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd').read_bytes();rows=[]
for stx in sorted((area/'overlay/usr/local/share/gemini/res/stx').glob('*.stx')):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,0x30000);u.mem_map(0x60000000,0x200000);sp=0x50028000;context=0x50002000;buffer=0x50004000
 u.mem_write(buffer,swd);u.mem_write(0x60000000,stx.read_bytes());u.mem_write(0x70b8dc+68,struct.pack('<II',0x60000000,0x60000000));events=[];measurements=[];heights=[];display_text=[];font_position=[0];heap=[0x62000000]
 u.mem_map(0x61000000,(len(font)+4095)&~4095);u.mem_write(0x61000000,font);u.mem_map(0x62000000,0x1000000)
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
  elif pc in (0xdb08,0xdc88):
   if pc==0xdb08:result=len(string(a[0]))
   else:
    text=string(a[1])[:a[2]];uc.mem_write(a[0],text+bytes(a[2]-len(text)));result=a[0]
  elif pc==0xe09c:
   if string(a[0])==b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf':
    assert a[1]==0;font_position[0]=0;uc.reg_write(UC_ARM_REG_R0,7);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert string(a[0])==b'/usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd' and a[1]==0
   events.append('open');result=8
  elif pc==0xe234:
   assert a[:2]==[3,8];uc.mem_write(a[2],bytes(88));uc.mem_write(a[2]+44,struct.pack('<I',len(swd)))
  elif pc==0xe48c:
   assert a[0]==7;chunk=font[font_position[0]:font_position[0]+a[2]];font_position[0]+=len(chunk)
   if chunk:uc.mem_write(a[1],chunk)
   result=len(chunk)
  elif pc==0xe324:assert a[0]==30;result=4096
  elif pc==0xd808:result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
  elif pc==0xdafc:
   assert a[2:]==[1,1]
   if word(uc.reg_read(UC_ARM_REG_SP))==7:
    assert a[1]==(len(font)+4095)&~4095;result=0x61000000
   else:
    assert word(uc.reg_read(UC_ARM_REG_SP))==8 and a[1]==4096;events.append('map');result=buffer
  elif pc==0xd934:assert a==[buffer,4096,0,0] or a[:2]==[buffer,4096];events.append('unmap')
  elif pc==0xd6f4:assert a[0]==8;events.append('close')
  elif pc in (0xda0c,0xd6b8):
   left=string(a[0]);right=string(a[1])
   if pc==0xd6b8:left=left[:a[2]];right=right[:a[2]]
   result=(left>right)-(left<right)
  elif pc==0xd754:
   assert a[1]==0 and a[2]==10;m=re.match(rb'[+-]?\d+',string(a[0]));result=int(m.group()) if m else 0
  elif pc==0xf3ba8:
   assert a[:2]==[0x13ad1107,180]
   expected='Homebrew unavailable.\nCheck HOMEBREW.'.encode('utf-16le')+b'\0\0'
   assert bytes(uc.mem_read(a[2],len(expected)))==expected
   measurements.append({'font_id':hex(a[0]),'width':a[1]});return # execute original metric function
  elif pc==0x10a448:heights.append(a[1])
  elif pc in (0xf56b4,0xf3af8,0xee9e4,0x10a938,0x10a9a4,0x10a24c):pass
  elif pc==0xf577c:
   assert a[3]==59;uc.mem_write(word(uc.reg_read(UC_ARM_REG_SP)+4),struct.pack('<I',0x50010000))
  elif pc==0xf3694:
   assert a[0]==0x50010000
   expected='Homebrew unavailable.\nCheck HOMEBREW.'.encode('utf-16le')+b'\0\0'
   assert bytes(uc.mem_read(a[1],len(expected)))==expected;display_text.append(True)
  else:
   symbol=next((sym.name for sym in ELFFile(io.BytesIO(raw)).get_section_by_name('.dynsym').iter_symbols() if sym['st_value']==pc),None) if 0xd410<=pc<0xe4e0 else None
   if symbol in ('memcpy','memmove'):uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
   elif symbol=='strcpy':uc.mem_write(a[0],string(a[1])+b'\0');result=a[0]
   elif symbol in ('malloc','calloc'):
    n=a[0] if symbol=='malloc' else a[0]*a[1];assert 0<n and heap[0]+n<0x63000000;result=heap[0];heap[0]+=(n+7)&~7
   elif symbol=='free':pass
   elif symbol:raise AssertionError('Unsupported import '+str(symbol))
   else:return
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 font_path=0x50015000;u.mem_write(font_path,b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf\0')
 u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,font_path);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50029000)
 u.emu_start(0x129d84,0x50029000,count=300000);assert u.reg_read(UC_ARM_REG_PC)==0x50029000 and u.reg_read(UC_ARM_REG_R0)==0
 u.reg_write(UC_ARM_REG_R0,99999);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50029000)
 u.emu_start(0x10a544,0x50029000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x50029000 and u.reg_read(UC_ARM_REG_SP)==sp
 pointer=u.reg_read(UC_ARM_REG_R0);text='Homebrew unavailable.\nCheck HOMEBREW.'.encode('utf-16le')+b'\0\0';assert bytes(u.mem_read(pointer,len(text)))==text
 assert events==['open','map','unmap','close']
 descriptor=elf_build['symbols']['hb_error_descriptor'];parent=0x50008000
 assert bytes(u.mem_read(descriptor,48))==struct.pack('<12I',745,99999,1,0,0,0,0,0,0,0,0,2);u.mem_write(parent+0xaf4,struct.pack('<I',1))
 u.reg_write(UC_ARM_REG_R0,parent);u.reg_write(UC_ARM_REG_R1,descriptor);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50029000)
 u.emu_start(0x10ac20,0x50029000,count=1000000);assert u.reg_read(UC_ARM_REG_PC)==0x50029000 and u.reg_read(UC_ARM_REG_SP)==sp
 assert len(measurements)==1 and heights==[80] and display_text==[True]
 assert word(parent+0xaf4)==2 and word(0x70c5f0+20)==2
 assert len(events)%4==0 and all(events[i:i+4]==['open','map','unmap','close'] for i in range(0,len(events),4))
 rows.append({'stx':stx.name,'events':events,'text_exact':True,'measurement_calls':measurements,'height_with_real_font':heights[0],'real_font_line_count':word(0x70c5f0+20),'real_font_max_line_width':word(0x70c5f0+8)})
assert len(rows)==11
report={'passed':True,'stock_sid_file_loader_parser_and_lookup_executed':True,'actual_candidate_descriptor_used':True,'candidate_sha256':elf_build['candidate_sha256'],'cases':rows,'file_stat_mapping_libc_services_mocked':True,'stx_context_is_fixture':True,'font_measurement_call_verified':True,'actual_font_metrics_verified':True,'metric_functions_not_interposed':True,'font_sha256':hashlib.sha256(font).hexdigest(),'graphics_layout_helpers_mocked':True,'screen_render_verified':False,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'work/home-feedback-resource-review-2/real-font-layout-report.json').write_text(json.dumps(report,indent=2)+'\n');print('11 compact resource/layout paths passed with original LCF metric functions')
