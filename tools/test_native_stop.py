"""Production stop adapter through the actual stock event-post ARM body."""
import hashlib,io,json,struct,subprocess,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/native-stop'/str(time.time_ns());out.mkdir(parents=True)
fixture=out/'fixture.c';fixture.write_text('unsigned image_valid=1;int xw_native_rf_image_valid(void){return image_valid;}')
helper=out/'stop.elf';source='runtime/platform/wireless/native_stop.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x51000000,-e,xw_native_rf_stop_request',source,str(fixture),'-o',str(helper)],cwd=ROOT,check=True)
symbols={s.name:s['st_value'] for s in ELFFile(io.BytesIO(helper.read_bytes())).get_section_by_name('.symtab').iter_symbols()}
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
cases=[]
for scenario in ('empty','duplicate','occupied','lock-refused','image-refused'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x50ff0000,0x40000);u.mem_map(0x50000000,4096);u.mem_map(0x60000000,65536)
 for raw in (stock,helper.read_bytes()):
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 def put(a,n):u.mem_write(a,struct.pack('<I',n))
 cursor=word(0xa590c);slots=word(0xa5910);u.mem_write(cursor,b'\0\0');u.mem_write(slots,bytes(500*32))
 if scenario=='duplicate':u.mem_write(cursor,b'\1\0');u.mem_write(slots,b'\1');put(slots+4,0x4c0006)
 if scenario=='occupied':u.mem_write(slots,b'\1');put(slots+4,0x123456)
 if scenario=='image-refused':put(symbols['image_valid'],0)
 locks=[];signals=[]
 def hook(uc,pc,size,unused):
  if pc==0xa6c9c:locks.append('lock');answer=0 if scenario=='lock-refused' else 1
  elif pc==0xa6dec:locks.append('unlock');answer=0
  elif pc==0xa6c18:signals.append('signal');answer=0
  else:return
  uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(symbols['xw_native_rf_stop_request'],0x50000000,count=30000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 answer=u.reg_read(UC_ARM_REG_R0)
 expected=0 if scenario in ('empty','duplicate') else 0xfffffffc if scenario=='image-refused' else 1
 assert answer==expected,(scenario,hex(answer))
 if scenario=='empty':
  assert u.mem_read(slots,1)==b'\1' and word(slots+4)==0x4c0006 and word(slots+8)==0xfffe
  assert bytes(u.mem_read(slots+12,20))==bytes(20) and u.mem_read(cursor,2)==b'\1\0' and signals==['signal']
 if scenario=='duplicate':assert u.mem_read(cursor,2)==b'\1\0' and u.mem_read(slots+32,1)==b'\0' and not signals
 if scenario=='image-refused':assert not locks and not signals
 cases.append(dict(case=scenario,result=answer,locks=locks,signals=signals))
report=dict(passed=True,device_accessed=False,firmware_created=False,arm_cases=len(cases),cases=cases,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (source,'tools/test_native_stop.py')},
 limits=['Original event-post body and production C sender execute; mutex/signal outcomes and image qualification are fixtures.',
 'Native worker queue scheduling, stop completion, physical radio and lock ordering are not qualified here.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
