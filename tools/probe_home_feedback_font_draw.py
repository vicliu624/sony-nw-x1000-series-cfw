"""Observe stock renderer initialization up to unsupported services, PC only."""
from pathlib import Path
import io,json,hashlib,struct,sys,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UcError
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'work/home-feedback-font-draw-probe-8';out.mkdir(exist_ok=False);sys.path.insert(0,str(ROOT));from scripts.upg import unpack;from scripts.resources import parse_stx
package=(ROOT/'dist/0.1.0-dev.16/diagnostic-review-5/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes();assert hashlib.sha256(package).hexdigest()=='11f466c94d091c2a7bfb905beb3d94f81ab540dcc0bc33c38597c2ae34daa8cd'
_,components=unpack(package,require_stock=False);archive=tarfile.open(fileobj=io.BytesIO(components[3]),mode='r:gz');raw=archive.extractfile('./usr/local/bin/SpiderApp').read();assert hashlib.sha256(raw).hexdigest()=='91b28344c4839e0dc9ce967ce6101634c23dfc6b794c316acc4f4e3c3fe28d16'
message=parse_stx(archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-en.stx').read())[7309]
elf=ELFFile(io.BytesIO(raw));names={s['st_value']:s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_value']}
plt=elf.get_section_by_name('.plt');u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,0x20000);u.mem_map(0x60000000,0x1000000);sp=0x50018000;path=0x50001000;u.mem_write(path,b'/usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf\0');import tarfile
font=archive.extractfile('./usr/local/share/gemini/res/font/ucs2-dev-en-eu-jp-kr.lcf').read()
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
init_return=u.reg_read(UC_ARM_REG_R0)
pixels=0x63001000;surface=0x50008000;pointer=0x50004000;width=240;height=432;size=width*height*4
u.mem_map(0x63000000,0x80000);u.mem_write(0x63000000,b'\xa5'*0x80000);background=b'\x30\x20\x10\xff';u.mem_write(pixels,background*(width*height))
u.mem_write(surface,struct.pack('<8I',width,height,16,0,0,0,0,pixels));u.mem_write(pointer,message.encode('utf-16le')+b'\0\0')
def call(address,args,stack=None):
 for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x50019000)
 if stack is not None:u.mem_write(sp,struct.pack('<I',stack))
 try:u.emu_start(address,0x50019000,count=5000000)
 except (UcError,AssertionError) as error:stop.append({'reason':type(error).__name__,'text':str(error),'pc':hex(u.reg_read(UC_ARM_REG_PC))})
 return u.reg_read(UC_ARM_REG_PC)==0x50019000
draw_trace=[];clip_trace=[]
def observe(uc,pc,size,_):
 if pc in (0x12ab50,0x12ab70,0x12abc0,0x12ac1c,0x12ac7c,0x12acd0,0x12ace0,0x12ad20,0x12b344) and len(clip_trace)<240:
  clip_trace.append({'pc':hex(pc),'r3':uc.reg_read(UC_ARM_REG_R3),'r0':uc.reg_read(UC_ARM_REG_R0),'r6':uc.reg_read(UC_ARM_REG_R6)})
 if pc in (0x12a848,0x12a900,0x12a918,0x12a924,0x12a934,0x12b344) and len(draw_trace)<500:
  draw_trace.append({'pc':hex(pc),'r0':uc.reg_read(UC_ARM_REG_R0),'r2':uc.reg_read(UC_ARM_REG_R2),'r3':uc.reg_read(UC_ARM_REG_R3),'glyph':uc.reg_read(UC_ARM_REG_R9)})
u.hook_add(UC_HOOK_CODE,observe)
style_returned=call(0x129c18,[0,0x13ad1107,0,0])
rectangle=0x5000a000;bounds=0x5000b000;u.mem_write(rectangle,struct.pack('<4i',20,30,199,99))
u.mem_write(sp,struct.pack('<2I',surface,bounds))
draw_returned=call(0x12bc14,[0,0x13ad1107,rectangle,pointer])
image=bytes(u.mem_read(pixels,size));locations=[i//4 for i in range(0,size,4) if image[i:i+4]!=background];bbox=[min(i%width for i in locations),min(i//width for i in locations),max(i%width for i in locations),max(i//width for i in locations)] if locations else None;changed=sum(image[i:i+4]!=background for i in range(0,size,4));guards=bytes(u.mem_read(pixels-32,32))==b'\xa5'*32 and bytes(u.mem_read(pixels+size,32))==b'\xa5'*32
(out/'frame.argb').write_bytes(image)
passed=init_return==0 and style_returned and draw_returned and not stop and changed>0 and guards and 20<=bbox[0]<=bbox[2]<=199 and 30<=bbox[1]<=bbox[3]<=99
if passed:
 import zlib,binascii
 rgba=bytearray(size)
 for i in range(0,size,4):rgba[i:i+4]=bytes((image[i+2],image[i+1],image[i],image[i+3]))
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
 scanlines=b''.join(b'\0'+bytes(rgba[y*width*4:(y+1)*width*4]) for y in range(height))
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scanlines))+chunk(b'IEND',b'')
 (out/'frame.png').write_bytes(png)
j={'passed':passed,'draw_trace':draw_trace,'clip_trace':clip_trace,'layout_bounds':struct.unpack('<8I',u.mem_read(bounds,32)),'scope':'Native LCF glyph drawing to constructed PC ARGB32 surface; not Sony GUI or hardware','initialization_return':init_return,'style_returned':style_returned,'draw_returned':draw_returned,'changed_pixels':changed,'guards_unchanged':guards,'stop':stop,'events':events,'candidate_elf_sha256':hashlib.sha256(raw).hexdigest(),'candidate_upg_sha256':hashlib.sha256(package).hexdigest(),'message':message,'changed_pixel_bbox':bbox,'font_sha256':hashlib.sha256(font).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidate5_changed':False,'physical_display_verified':False}
(out/'report.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({k:j[k] for k in ['passed','changed_pixels','guards_unchanged','stop','draw_returned']},indent=2))
