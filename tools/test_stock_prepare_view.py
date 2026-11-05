"""Actual ARM read-only pre-prepare view on a fresh composed bridge image."""
import contextlib,hashlib,io,json,runpy,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
work=ROOT/'work/stock-prepare-view'/str(time.time_ns());work.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):
    composed=runpy.run_path(str(ROOT/'tools/test_player_prepare_composition.py'))
native=composed['artifact'].read_bytes()
sources=['runtime/platform/player/stock_prepare_view.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','tools/fixtures/player_prepare_view.c']
binary=work/'view.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()};rows=[]
cases=[('valid',0),('native-started',-4),('pending',-4),('overflow',-8),('wrong-tracker',-3),('bad-root',-1),('bad-command',-1),('zero-epoch',-1),('wrong-bind-owner',-4),('wrong-image',-3),('changed-bridge',-3),('changed-action',-3),('changed-finalizer',-3)]
for case,expected in cases:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 segments=[s for elf in (ELFFile(io.BytesIO(native)),helper) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 ranges=sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments)
 merged=[]
 for start,end in ranges:
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 for s in segments:u.mem_write(int(s['p_vaddr']),s.data())
 area=0x71000000;u.mem_map(area,65536);done=area+0xff00
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
 put(0x613e64,3 if case=='native-started' else 1);put(0x613e68,0);put(0x613eac,1)
 put(0x613e8c,0xdead0001 if case=='wrong-tracker' else 0x66efe8)
 put(0x66efe8,33 if case=='overflow' else 1 if case=='pending' else 0)
 if case=='wrong-bind-owner':put(symbols['xw_test_thread'],18)
 if case=='wrong-image':put(symbols['xw_test_loaded'],0)
 for name,address in (('changed-bridge',0x4d7fc0),('changed-action',0x718e0),('changed-finalizer',0x10d80)):
  if case==name:u.mem_write(address,bytes([u.mem_read(address,1)[0]^1]))
 before=(bytes(u.mem_read(0x613e60,0x100)),bytes(u.mem_read(0x66efe8,132)))
 def call(name,*args):
  for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):u.reg_write(register,value)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(symbols[name],done,count=2000000);assert u.reg_read(UC_ARM_REG_PC)==done
  value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
 result=call('test_bind_zero') if case=='zero-epoch' else call('test_bind',0xdead0001 if case=='bad-root' else 0x613e60,7 if case=='bad-command' else 3)
 assert result==expected,(case,result)
 if not result:
  assert call('test_bind',0x613e60,3)==-4 and call('test_check')==0 and call('test_stale')==-5
  for address,value,restored in ((0x613e64,6,1),(0x613e68,1,0),(0x613eac,0,1)):
   put(address,value);assert call('test_check')==-5;put(address,restored)
  put(0x66efe8,1);assert call('test_check')==-4;put(0x66efe8,0)
  put(0x613e8c,0xdead0001);assert call('test_check')==-3;put(0x613e8c,0x66efe8)
  put(symbols['xw_test_thread'],18);assert call('test_check')==-4 and call('test_unbind')==-4
  put(symbols['xw_test_thread'],17);assert call('test_unbind')==0 and call('test_check')==-7
 assert (bytes(u.mem_read(0x613e60,0x100)),bytes(u.mem_read(0x66efe8,132)))==before
 rows.append(dict(case=case,result=result,native_root_and_tracker_unchanged=True))
report=dict(passed=True,device_accessed=False,read_only=True,actual_arm_view_and_hash_guards=True,
            native_identity_and_owner_modeled=True,cases=rows,input_image_sha256=hashlib.sha256(native).hexdigest(),
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/stock_prepare_view.h','tools/fixtures/stock_host_image.c','tools/test_stock_prepare_view.py']},
            limits=['Root/tracker data, dladdr and qualified owner are fixtures; no hardware or live lifecycle binding.',
                    'Observed consistency only: no ABA detection, Root reference retention, token registration, original prepare call or installed dispatcher.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
