"""Pinned main-loop instruction -> PID shim -> actual provider owner binding."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from build_player_host import ROOT,CORE_SOURCES as SOURCES,build
_,candidate,build_report=build();work=ROOT/'work/player-host';artifact=work/'anchor-consumer.arm'
fixture='tools/fixtures/player_host_anchor.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*SOURCES,fixture,'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
stock=candidate.read_bytes();helper=artifact.read_bytes();elf=ELFFile(io.BytesIO(helper));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
cases=[]
for scenario in ('anchor','wrong-thread','bind-incompatible','unmodified','wrong-image','changed-following','fallback'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for raw in (stock,helper):
  for segment in ELFFile(io.BytesIO(raw)).iter_segments():
   if segment['p_type']!='PT_LOAD':continue
   a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
 stack,done=0x70000000,0x72000000;u.mem_map(stack,65536);u.mem_map(done,4096)
 def put(a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(a):return struct.unpack('<I',u.mem_read(a,4))[0]
 put(0x612c48,0)
 if scenario=='unmodified':put(0xff3c,0xeb025a89)
 if scenario=='changed-following':put(0xff40,0)
 if scenario=='wrong-image':put(symbols['xw_test_loaded'],0)
 if scenario=='bind-incompatible':u.mem_write(0x275e00,bytes([u.mem_read(0x275e00,1)[0]^1]))
 if scenario=='fallback':put(symbols['test_resolve'],0)
 stops=[done];fallbacks=[];plt_calls=[]
 def hook(uc,pc,size,data):
  if pc in stops:uc.emu_stop();return
  if pc==0xda84:plt_calls.append(pc);uc.reg_write(UC_ARM_REG_PC,symbols['getpid'])
 def syscall(uc,number,data):
  assert get(uc.reg_read(UC_ARM_REG_PC)-4)==0xef900014
  fallbacks.append(number);uc.reg_write(UC_ARM_REG_R0,4321)
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,syscall)
 def call(address,return_to=done):
  stops[:]=[return_to];u.reg_write(UC_ARM_REG_SP,stack+65520);u.reg_write(UC_ARM_REG_LR,return_to)
  # Deliberately invalid pointer-looking values: the argument-free fallback
  # must not interpret these as addresses or write through them.
  u.reg_write(UC_ARM_REG_R0,0xdead0001);u.reg_write(UC_ARM_REG_R1,0xbeef0001)
  try:u.emu_start(address,return_to+4,count=30000000)
  except Exception as error:raise AssertionError((scenario,hex(address),hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)))) from error
  assert u.reg_read(UC_ARM_REG_PC)==return_to
  return u.reg_read(UC_ARM_REG_R0)
 call(symbols['host_initialize'])
 assert call(symbols['xw_player_host_pid_resolved'])==int(scenario!='fallback')
 # The direct call covers a coincidental FF40 caller in an unmodified image.
 result=call(symbols['getpid'] if scenario=='unmodified' else 0xff3c,0xff40)
 active=scenario in ('anchor','wrong-thread','fallback')
 assert call(symbols['xw_player_host_anchor_ready'])==int(active),scenario
 if active:
  assert result==0 and get(symbols['test_dispatch_calls'])==1 and get(symbols['test_initialized'])==1
  assert get(symbols['test_poll_result'])==0xfffffffe # uninitialized stock AudioC is unavailable
  if scenario=='wrong-thread':
   put(symbols['xw_test_thread'],18);assert call(0xff3c,0xff40)==0 and get(symbols['test_dispatch_calls'])==1
   put(symbols['xw_test_thread'],17)
  for _ in range(200):assert call(0xff3c,0xff40)==0
  assert get(symbols['test_dispatch_calls'])==201
 else:
  assert get(symbols['test_dispatch_calls'])==0
  assert result==(0 if scenario=='bind-incompatible' else 4321)
 before=get(symbols['test_dispatch_calls']);assert call(symbols['getpid'])==4321
 assert get(symbols['test_dispatch_calls'])==before and get(symbols['test_errno'])==1234
 if scenario=='fallback':assert fallbacks and get(symbols['test_pid_calls'])==0
 else:assert not fallbacks
 cases.append(dict(case=scenario,provider_ready=active,dispatches=get(symbols['test_dispatch_calls']),original_plt_calls=len(plt_calls),fallback_calls=len(fallbacks)))
report=dict(passed=True,device_accessed=False,original_anchor_instruction=True,actual_provider_binding=True,stock_app_booted=False,cases=cases,candidate_sha256=build_report['candidate_sha256'],
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES+[fixture,'tools/fixtures/stock_provider_host.c','tools/fixtures/stock_host_image.c','tools/test_player_host_anchor.py']},
 limits=['Loaded-image identity, RTLD_NEXT, original PID PLT routing and the kernel PID result are modeled.',
         'The patched ARM call, guarded shim, actual native provider binding and client snapshot call execute; stock AudioC is intentionally uninitialized.',
         'No endpoint, worker, device execution, flash package or sleep/USB validation is provided.'])
(work/'anchor-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
