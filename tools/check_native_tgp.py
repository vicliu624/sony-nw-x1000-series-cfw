"""Execute original TGP/TXD reader on stock TEXGRP00 through virtual file services."""
import runpy,struct,json,hashlib,sys,argparse
p=argparse.ArgumentParser();p.add_argument("--register-images",action="store_true");p.add_argument("--catalog-map",action="store_true");args=p.parse_args();args.register_images=args.register_images or args.catalog_map
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];root=n['ROOT']
sys.path.insert(0,str(root/'scripts'));from resources import parse_tgp
raw=(root/'work/resource-analysis/TEXGRP00.DAT').read_bytes();expected=parse_tgp(raw)
assert hashlib.sha256(raw).hexdigest()=='32a0a248a9bc72eab858a3a147ab4c720e90d7294fade564ba0c5b722c5250f3'
base=0x70000000;size=(len(raw)+4095)&~4095;u.mem_map(base,size);u.mem_write(base,raw)
ctx,out,path,count=0x60010000,0x60011000,0x60012000,0x60013000
u.mem_write(path,b'/usr/local/share/GUI/skinRom/TEXGRP00.DAT\0');services=[];unmaps=[];closes=[]
def hook(uc,pc,size,data):
 if pc not in (0xe324,0x132774,0x132834,0x132800,0xe09c,0xdafc,0xd6b8,0xd808,0xd574,0xd85c,0xdb08,0x3397f4,0xd934,0xd6f4,0x3387c0,0x338dd4):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
 services.append(hex(pc))
 if pc in (0x3387c0,0x338dd4):result=1 if pc==0x338dd4 else 0
 elif pc==0xd85c:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));result=a[0]
 elif pc==0xdb08:result=len(bytes(u.mem_read(a[0],128)).split(b'\0')[0])
 elif pc==0x3397f4:
  fmt=bytes(u.mem_read(a[3],128)).split(b'\0')[0].decode();value=n['word'](uc.reg_read(UC_ARM_REG_SP));text=(fmt%value).encode();assert len(text)<a[1];u.mem_write(a[0],text+b'\0');result=len(text)
 elif pc==0xd934:assert a[:2]==[base,(len(raw)+4095)&~4095];unmaps.append(a[:2])
 elif pc==0xd6f4:assert a[0]==17;closes.append(a[0])
 elif pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
 elif pc==0xe324:assert a[0]==30;result=4096
 elif pc==0x132774:assert bytes(u.mem_read(a[2],128)).split(b'\0')[0]==bytes(u.mem_read(path,128)).split(b'\0')[0]
 elif pc==0x132834:assert a[3]==32;u.mem_write(a[2],raw[:32])
 elif pc==0xe09c:assert bytes(u.mem_read(a[0],128)).split(b'\0')[0]==bytes(u.mem_read(path,128)).split(b'\0')[0] and a[1]==0;result=17
 elif pc==0xdafc:assert a[:4]==[0,(len(raw)+4095)&~4095,3,2];result=base
 elif pc==0xd808:
  assert a[1];result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
 elif pc==0xd6b8:
  left=bytes(u.mem_read(a[0],a[2])).split(b'\0')[0];right=bytes(u.mem_read(a[1],a[2])).split(b'\0')[0];result=0 if left==right else 1
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
assert n['call'](0x1267c4,(ctx,path,count,0))==0
assert n['word'](count)==len(expected)
records=[]
for ref in expected:
 assert n['word'](ctx+20)==base+ref['offset']
 assert n['call'](0x126968,(ctx,ref['index'],out,0))==0
 w,h,fmt=struct.unpack('<3I',u.mem_read(out,12))
 assert [w,h,fmt&0xffff]==[ref['width'],ref['height'],ref['format']]
 pointer_field={2:16,4:20,8:24,16:28}[ref['format']]
 assert n['word'](out+pointer_field)==base+ref['offset']+32
 records.append({'index':ref['index'],'width':w,'height':h,'format':fmt,'payload_offset':ref['offset']+32})
assert n['word'](ctx+20)==base+len(raw)
r={'SpiderApp_sha256':n['digest'],'asset_file_sha256':hashlib.sha256(raw).hexdigest(),'scope':'Original1267c4/126968 file header and TXD iteration; virtual file/mmap/libc services','record_count':len(records),'asset51':records[51],'records':records,'virtual_service_entries':services,'limits':['No image registration, asset-group lookup, color conversion or actual drawing.','Mapped bytes come from local stock resource file; filesystem/mmap services virtual.']}
if args.register_images:
 manager=0x7a0660;group_out=0x60014000
 assert n['call'](0x132938,(manager+0x18284,1,0,0))==0
 assert n['call'](0x132938,(manager+0x2f28c,139,0,0))==0
 if not args.catalog_map:assert n['call'](0x133060,(group_out,2,0,0))==0 and n['word'](group_out)==0
 def invoke(pc,values):
  for reg,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(reg,v)
  u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(pc,0x50000000,count=2000000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
  return u.reg_read(UC_ARM_REG_R0)
 if args.catalog_map:
  catalog=n['call'](0xf647c,(0,0,0,0));invoke(0xf6488,(catalog,))
  u.mem_write(0x60008000,struct.pack('<I',1))
  assert invoke(0xf6a58,(catalog,0,0,0))==0
  assert all(n['word'](catalog+0x11c+i*4)==i for i in range(139))
  resolved=0x60015000
  assert invoke(0xf6c58,(catalog,0,51,resolved))==0 and n['word'](resolved)==51
  r['native_catalog_mapping']={'group':0,'mapped_entries':139,'asset51_handle':51,'host_mapping_writes':False,'loader':'0xf6a58','lookup':'0xf6c58'}
 else:assert invoke(0x132f40,(path,0,0))==0
 assert n['word'](manager+4)==139 and n['word'](manager+0x30294)==139
 image51=manager+0x192a4+51*88
 assert list(struct.unpack('<3I',u.mem_read(image51,12)))==[78,78,0x10008]
 assert n['word'](image51+24)==base+expected[51]['offset']+32
 r['native_registration']={'group':0,'images':139,'asset51_handle':51,'asset51_size':[78,78],'host_image_handle_writes':False}
 if args.catalog_map:assert invoke(0xf6c30,(catalog,0))==0
 else:assert invoke(0x133088,(0,))==0
 assert n['word'](manager)==0 and n['word'](manager+0x30294)==0
 assert len(unmaps)==1 and closes==[17]
 r['native_release']={'groups_after':0,'images_after':0,'mapped_file_release_calls':unmaps,'close_calls':closes}
 r['scope']='Original TGP parser plus native image/group registration and complete group release'
 r['limits']=['Group/image pool capacities1/139 supplied; file, mmap and libc services virtual.', 'No catalog mapping, Home reconstruction, image color conversion or drawing.']
if args.catalog_map:
 r['scope']='Original packed DAT loading,139 asset catalog mappings,lookup and group release'
 r['limits']=['File/mmap/libc and directory enumeration services virtual; packed DAT bytes are real.', 'No Home integration, color conversion or actual display.']
(root/('sources/native-tgp00-catalog.json' if args.catalog_map else 'sources/native-tgp00-registration.json' if args.register_images else 'sources/native-tgp00-reader.json')).write_text(json.dumps(r,indent=2)+'\n');print('Original reader verified',len(records),'TXD records; asset51:',records[51])
