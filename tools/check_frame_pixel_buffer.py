"""Native format2 pixel-buffer allocation/release; file and mapping services virtual."""
import runpy,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];u.mem_map(0x62000000,0x40000);header=0x60014000;ops=[]
def string(p):return bytes(u.mem_read(p,128)).split(b'\0')[0].decode()
def hook(uc,pc,size,data):
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];answer=0
 if pc==0xe09c:
  assert string(a[0])=='/dev/zero' and a[1]==0;ops.append('open_dev_zero');answer=17
 elif pc==0xe324:assert a[0]==30;answer=4096
 elif pc==0xdafc:
  assert a==[0,208896,3,2],a
  sp=uc.reg_read(UC_ARM_REG_SP);assert n['word'](sp)==17 and n['word'](sp+4)==0
  ops.append('mmap_208896');answer=0x62000000
 elif pc==0xd6f4:assert a[0]==17;ops.append('close')
 elif pc==0xd934:
  assert a[:2]==[0x62000000,208896],a;ops.append('munmap_208896')
 elif pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);answer=a[0]
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
u.mem_write(0x62000000,b'\xa5'*0x40000)
n['call'](0x11f9d8,(header,0,0,0));assert n['word'](header+60)==0x12345678
assert n['call'](0x120220,(header,240,432,2))==0
assert n['word'](header+16)==0x62000000 and n['word'](header+40)==207360 and n['word'](header+8)==2
assert bytes(u.mem_read(0x62000000,207360))==bytes(207360)
assert bytes(u.mem_read(0x62000000+207360,208896-207360))==b'\xa5'*(208896-207360)
n['call'](0x11f904,(header,2,0,0));assert n['word'](header+8)==0
n['call'](0x11f904,(header,2,0,0));assert ops==['open_dev_zero','mmap_208896','close','munmap_208896'],ops
r={'SpiderApp_sha256':n['digest'],'scope':'Original image header/format2 allocation/release incl132a78/132b04; libc memory/files/mapping virtual','dimensions':[240,432],'logical_bytes':207360,'mapping_bytes_with_4096_page_fixture':208896,'operations':ops,'padding_not_cleared':True,'second_release_does_not_unmap':True,'limits':['Page size4096 and successful virtual mmap supplied, not device memory measurements.', 'No actual /dev/zero file, kernel mapping, textures, display output or frame integration in this checker.']}
Path(n['ROOT'],'sources/native-frame-pixel-buffer.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

