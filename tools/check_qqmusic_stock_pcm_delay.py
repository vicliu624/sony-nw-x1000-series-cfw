"""Replay original GETODELAY instructions; synthetic DMA position, no devices."""
from pathlib import Path
import hashlib,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
with (ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').open('rb') as f:symbols={s.name:s['st_value'] for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols()}
def run(active,queued,committed,partial,position,mode=2,copy_error=False,request=0x80045017):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0008000,0x400000);u.mem_write(0xc0008000,raw);u.mem_map(0x60000000,0x40000)
 file,state,out,fragments,result=0x60001000,0x60002000,0x60003000,0x60004000,0x60005000;end=0x6003f000;events=[]
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 put(file+28,mode);put(file+128,state);put(state,out);put(out+4,fragments);put(out+16,2);put(out+24,0);put(out+28,1024);put(out+36,queued);put(out+40,20)
 put(fragments,committed);put(fragments+8,0x100000);put(fragments+12,active);put(fragments+32,partial)
 before=bytes(u.mem_read(file,0x4000))
 def ret(v):u.reg_write(UC_ARM_REG_R0,v&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 def hook(uc,pc,size,context):
  if pc==end:uc.emu_stop();return
  if pc==symbols['memset']:
   uc.mem_write(uc.reg_read(UC_ARM_REG_R0),bytes([uc.reg_read(UC_ARM_REG_R1)&255])*uc.reg_read(UC_ARM_REG_R2));ret(0)
  elif pc==symbols['mp200_get_dma_pos']:
   assert uc.reg_read(UC_ARM_REG_R0)==20;events.append('dma_position_read');ret(0x100000+position)
  elif pc==symbols['__put_user_4']:
   assert uc.reg_read(UC_ARM_REG_R0)==result
   if not copy_error:put(result,uc.reg_read(UC_ARM_REG_R2))
   ret(-14 if copy_error else 0)
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR),(0,file,request,result,0x6003c000,end)):u.reg_write(r,v)
 u.emu_start(symbols['audio_ioctl'],0,count=10000);assert u.reg_read(UC_ARM_REG_PC)==end
 assert bytes(u.mem_read(file,0x4000))==before,'GETODELAY mutated stream state'
 rc=u.reg_read(UC_ARM_REG_R0);value=struct.unpack('<I',u.mem_read(result,4))[0]
 if request==0xc0045004:assert rc==0 and value==1024
 elif mode!=2:assert rc==0xffffffea
 elif copy_error:assert rc==0xfffffff2
 else:
  expected=(1024-(position if position<1024 else 1020)+queued*1024+partial) if active else ((queued-1)*1024+1024-committed+partial if queued and committed else queued*1024+partial)
  assert rc==0 and value==expected,(value,expected)
 return {'request':hex(request),'active_dma':active,'queued':queued,'committed':committed,'partial':partial,'position':position,'mode':mode,'copy_error':copy_error,'return_u32':rc,'delay_bytes':value,'events':events}
rows=[run(*args) for args in [(0,0,0,0,0),(0,0,0,128,0),(0,1,64,128,0),(0,2,0,0,0),(1,2,0,128,0),(1,2,0,128,512),(1,2,0,0,1024),(1,2,0,0,2048),(0,0,0,0,0,1),(0,0,0,0,0,2,True)]]
rows.append(run(0,0,0,0,0,request=0xc0045004))
report={'passed':True,'kernel_sha256':hashlib.sha256(raw).hexdigest(),'request':'0x80045017','cases':rows,'physical_device_accessed':False,'limits':['Original audio_ioctl executes, with userspace copy, memset and DMA position supplied.','Only valid allocated output-fragment state is covered. Do not query before first successful PCM write.','Read-only queue accounting is established, not physical DMA timing, acoustic completion or restoration.']}
w=ROOT/'work/qqmusic-preview-audio';w.mkdir(exist_ok=True);(w/'stock-pcm-delay-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows),'hardware_tested':False}))
