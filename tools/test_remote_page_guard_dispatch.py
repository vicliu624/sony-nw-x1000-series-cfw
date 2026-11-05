"""Composed native page -> actual PID shim/dispatch/guard; backend is a fixture."""
import argparse,hashlib,io,json,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from build_player_host import CORE_SOURCES
from review_managed_remote_profile import receipt,private,digest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True);args=parser.parse_args()
rp,review=receipt(args.review);path=private(review['artifact']);assert digest(path)==review['sha256']
header=private(review['guard_profile']);assert digest(header)==review['guard_profile_sha256']
out=ROOT/'work/remote-page-guard-dispatch'/str(time.time_ns());out.mkdir(parents=True)
fixture=out/'fixture.c';fixture.write_text('''#include "tools/fixtures/player_host_anchor.c"
unsigned test_ui_requests;
uint32_t xw_player_host_remote_page_request(uint32_t operation,uint32_t row){
 (void)row;test_ui_requests++;test_errno=99;
 return operation==1?0x57530001u:0x57520000u;
}
''')
sources=CORE_SOURCES+['runtime/platform/player/remote_page_guard.c']
binary=out/'guard.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DXW_PLAYER_NATIVE_REMOTE_SETTINGS','-include',str(header),'-I.','-I'+str(header.parent),'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,str(fixture),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
segments=[s for image in (ELFFile(io.BytesIO(path.read_bytes())),helper) for s in image.iter_segments() if s['p_type']=='PT_LOAD']
merged=[]
for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
 if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
 else:merged.append((start,end))
for start,end in merged:u.mem_map(start,end-start)
u.mem_map(0x70000000,0x10000)
for s in segments:u.mem_write(s['p_vaddr'],s.data())
area=0x70000000;done=area+0xff00
put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
def hook(cpu,pc,size,unused):
 if pc==0xda84:cpu.reg_write(UC_ARM_REG_PC,symbols['getpid'])
u.hook_add(UC_HOOK_CODE,hook)
def call(target,args=(),return_to=done):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*args,0,0,0,0][:4]):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,area+0xe000);u.reg_write(UC_ARM_REG_LR,return_to)
 u.emu_start(symbols[target] if isinstance(target,str) else target,return_to,count=30000000)
 assert u.reg_read(UC_ARM_REG_PC)==return_to
 return u.reg_read(UC_ARM_REG_R0)
page_open=review['symbols']['wr_remote_page_open']
put(0x612c48,0) # Explicit unavailable AudioC fixture, as in the owner-anchor harness.
call('host_initialize')
put(symbols['test_errno'],77)
assert call(page_open)==0x0202 and not word(symbols['test_ui_requests'])
assert call(0xff3c,return_to=0xff40)==0
assert call('xw_player_host_anchor_ready')==1
assert call(page_open)==0xc201 and word(symbols['test_ui_requests'])==1
assert word(symbols['test_errno'])==77
put(symbols['xw_test_thread'],18)
assert call(page_open)==0x0202 and word(symbols['test_ui_requests'])==1
put(symbols['xw_test_thread'],17)
assert call('getpid',return_to=0x4d8078)==0xfffffffd # Legacy toggle guard rejects new callback pointer.
assert not word(symbols['test_settings_requests'])
assert call('getpid')==4321
rows=[]
for name,guards,checker in [('page',review['page_guards'],'xw_player_remote_page_image_valid'),('view',review['view_guards'],'xw_player_remote_view_image_valid')]:
 assert call(checker)==1
 for g in guards:
  address=int(g['address'],16);old=bytes(u.mem_read(address,1));u.mem_write(address,bytes([old[0]^1]))
  assert call(checker)==0
  u.mem_write(address,old);assert call(checker)==1
  rows.append(dict(kind=name,address=hex(address),mutation_refused=True))
# Corrupt metadata rather than the executing entry: no UI/backend request passes.
address=int(review['metadata_address'],16);old=bytes(u.mem_read(address,1));u.mem_write(address,bytes([old[0]^1]))
assert call(page_open)==0x0202 and word(symbols['test_ui_requests'])==1
u.mem_write(address,old)
put(symbols['xw_test_loaded'],0)
assert call(page_open)==0x0202 and word(symbols['test_ui_requests'])==1
put(symbols['xw_test_loaded'],1)
assert call(page_open)==0xc201 and word(symbols['test_ui_requests'])==2
assert word(symbols['test_errno'])==77
report=dict(passed=True,candidate_sha256=review['sha256'],actual_native_page_pid_shim_dispatch_guard=True,
 guard_profile_sha256=digest(header),helper_sha256=digest(binary),fixture_sha256=digest(fixture),
 host_owner_binding_executed=True,backend_fixture=True,ordinary_pid_preserved=True,errno_preserved=True,
 unbound_and_foreign_owner_refused=True,legacy_toggle_not_enqueued=True,guard_cases=rows,
 device_accessed=False,firmware_created=False,
 source_hashes={p:digest(ROOT/p) for p in sources+['runtime/platform/player/remote_page_guard.h','tools/test_remote_page_guard_dispatch.py','tools/fixtures/player_host_anchor.c','tools/fixtures/stock_provider_host.c','tools/fixtures/stock_host_image.c']},
 limits=['Owner/thread/loader identity and backend reply are fixtures; no real dynamic loader or physical provider runs.',
         'Actual guarded native call chain executes, but no production view adapter/observer/Wi-Fi entry guard is installed.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
