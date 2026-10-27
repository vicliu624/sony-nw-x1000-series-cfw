"""Replay stock setting -> GUI -> STX selection. File/font services virtual."""
from pathlib import Path
import io,json,hashlib,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85';elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x40000);ctx=0x60000000;seen=[]
def string(p):return bytes(u.mem_read(p,128)).split(b'\0')[0].decode()
def hook(uc,pc,size,data):
 if pc==0xe87f4:answer=ctx
 elif pc in (0x115f1c,0x1291a0):answer=0
 elif pc==0xec9c4:
  index=uc.reg_read(UC_ARM_REG_R1);pointer=struct.unpack('<I',u.mem_read(0x4f7900+index*4,4))[0];seen.append({'index':index,'path':string(pointer)});answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);rows=[];expected=['de','en','es','fr','it','pt','ru','jp','kr','cs','ct']
for setting,language in enumerate(expected):
 u.mem_write(ctx,bytes(0x40000));u.reg_write(UC_ARM_REG_R0,setting);u.reg_write(UC_ARM_REG_SP,0x6003f000);u.reg_write(UC_ARM_REG_LR,0x50000000);seen.clear();u.emu_start(0xb5034,0x50000000,count=100000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000;assert len(seen)==1 and seen[0]['path'].endswith('ucs2-dev-'+language+'.stx'),(setting,seen);rows.append({'setting':setting,'language':language,**seen[0]})
out=ROOT/'work/language-map-review';out.mkdir(exist_ok=True);report={'passed':True,'scope':'Stock b5034 -> eb340 -> ec44c; STX open boundary and font services virtual, no hardware','cases':rows,'english_setting':1,'japanese_setting':7};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
