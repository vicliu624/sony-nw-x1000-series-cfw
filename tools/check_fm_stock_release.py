"""Original MFM detach, stop request and deferred tuner-close contract. No hardware."""
from pathlib import Path
import io,json,struct,hashlib,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/stock-manager-runtime-probe/root/usr/local/bin/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(packed),mode='r:gz')as t:assert t.extractfile('./usr/local/bin/SpiderApp').read()==raw
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value']for s in elf.get_section_by_name('.dynsym').iter_symbols()};rows=[]
for close_error in [False,True]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for p in elf.iter_segments():
  if p['p_type']!='PT_LOAD':continue
  lo=p['p_vaddr']&~4095;hi=(p['p_vaddr']+p['p_memsz']+4095)&~4095;u.mem_map(lo,hi-lo);u.mem_write(p['p_vaddr'],p.data())
 u.mem_map(0x60000000,0x20000);top,listener,service,out,sentinel=0x60001000,0x60002000,0x60003000,0x60004000,0x6001f000
 device=service+36;worker=service+60;events=[];phase=''
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 put(top,listener);put(top+4,0x1111);put(listener+4,service);put(listener+8,0x2222);put(listener+16,0x3333)
 put(service+12,3);put(device+4,61);put(device+8,82500);put(worker,device);put(worker+4,1)
 def hook(uc,pc,size,data):
  if pc==sentinel:uc.emu_stop();return
  if pc==0x337c84:
   events.append({'phase':phase,'virtual_event_post':True});result=0
  elif pc==symbols['close']:
   assert uc.reg_read(UC_ARM_REG_R0)==61;events.append({'phase':phase,'virtual_close_fd':61,'returns_error':close_error});result=0xffffffff if close_error else 0
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(entry,r0,r1=0):
  for reg,value in [(UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,sentinel)]:u.reg_write(reg,value)
  u.emu_start(entry,0,count=5000);assert u.reg_read(UC_ARM_REG_PC)==sentinel
  return u.reg_read(UC_ARM_REG_R0)
 phase='MFM finalize';call(0x26e548,top)
 assert word(top)==word(top+4)==0 and word(listener+8)==word(listener+16)==0
 assert word(device+4)==61 and not events
 detached={'caller_references_cleared':True,'device_fd':word(device+4),'close_called':False}
 phase='stop request';result=call(0x26f44c,listener,out)
 assert result==0 and word(out)==0 and word(device+4)==61 and word(worker+8)&2
 assert events==[{'phase':'stop request','virtual_event_post':True}]
 requested={'api_return':result,'out_value':word(out),'pending_bits':word(worker+8),'device_fd':word(device+4),'close_called':False}
 phase='worker pending snapshot';call(0x26fb70,worker);assert word(worker+12)&2
 phase='worker close';processed=call(0x26fbbc,worker)
 assert processed==2 and word(device+4)==0xffffffff and word(device+8)==0
 assert events[-1]=={'phase':'worker close','virtual_close_fd':61,'returns_error':close_error}
 rows.append({'virtual_close_error':close_error,'finalize':detached,'stop_request':requested,'worker_result_bits':processed,'device_field_after_worker':'-1','events':events})
report={'passed':True,'spider_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,'finding':'MFM finalization clears references but does not close the tuner. Stop request returns success before worker processing; the worker later issues close and clears its fd field even when virtual close returns an error.','hardware_tested':False,'limits':['Object relationships, playing state3 and an active worker are fixtures, not actual device state.','The event post and libc close are replacements; no real thread, fd or tuner release occurs.','Pending-copy and worker calls are invoked explicitly after the stop call, not scheduled by an actual OS.','APF deactivation to MFM stop and the final completion/acknowledgement are not yet connected.']}
out=ROOT/'work/fm-radio-research/stock-release.json';out.write_text(json.dumps(report,indent=2)+'\n');print('Original MFM release: detach does not close; stop success precedes deferred worker close; close error is hidden in worker result.')
