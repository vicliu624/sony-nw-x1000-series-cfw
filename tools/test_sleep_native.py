"""Native sleep binding, real pinned getters/ack client, modeled radio and IPC."""
import hashlib,io,json,struct,subprocess,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/player-sleep-native'/str(time.time_ns());out.mkdir(parents=True)
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
sources=['runtime/platform/player/'+n for n in ('sleep_native.c','sleep_host.c','sleep_retirement.c','stock_image.c')]+['runtime/native/sha256.c','tools/fixtures/sleep_native.c']
binary=out/'native.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()};rows=[]
for case in ('ready','initial-main','state-seven','inactive-main','native-inactive','native-inactive-initial','bad-callsite','wrong-owner','bad-image','root-changed','sequence-changed','main-changed','ack-error','restore-ready','restore-state-seven','restore-no-begin','restore-sequence','restore-root','restore-rejected','restore-wait','restore-usb','restore-native-queries'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);segments=[s for e in (ELFFile(io.BytesIO(raw)),helper) for s in e.iter_segments() if s['p_type']=='PT_LOAD'];merged=[]
 for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
  if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
  else:merged.append((start,end))
 for start,end in merged:u.mem_map(start,end-start)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x71000000,65536);done=0x7100ff00
 def put(address,value):u.mem_write(address,struct.pack('<I',value))
 def word(address):return struct.unpack('<I',u.mem_read(address,4))[0]
 main_word=0x102 if case in ('initial-main','native-inactive-initial') else 0x703 if case in ('state-seven','restore-state-seven') else 0x202 if case in ('inactive-main','native-inactive') else 0x403
 for a,v in ((0x682cd8,0x682cdc),(0x682cdc,main_word),(0x820f68,1),(0x820f6c,1 if case.startswith('native-inactive') else 2),(0x820f74,55),(0x820f78,500),(0x820f7c,5),(0x613e64,7),(0x613e68,0),(0x613eac,1),(0x613e8c,0x66efe8),(0x66efe8,0)):put(a,v)
 packets=[]
 def hook(cpu,pc,size,unused):
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
  if pc==0x268c9c:
   packet=list(struct.unpack('<5I',cpu.mem_read(args[2],20)));assert packet==[20,word(0x820f7c)-1,1,18,55];packets.append(packet)
  elif pc==0x268d48:cpu.mem_write(args[1],struct.pack('<4I',16,packets[-1][1],18,0x1d04 if case=='ack-error' else 0));put(args[3],16)
  elif pc not in (0xb00bc,0x33b918,0x33b83c,0x337a80,0x337ae8):return
  cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def call(name,*args):
  for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):u.reg_write(reg,value)
  u.reg_write(UC_ARM_REG_SP,0x7100f000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(symbols[name],done,count=3000000);assert u.reg_read(UC_ARM_REG_PC)==done
  result=u.reg_read(UC_ARM_REG_R0);return result if result<0x80000000 else result-0x100000000
 if case=='wrong-owner':put(symbols['xw_test_thread'],18)
 if case=='bad-image':put(0xb03e8,word(0xb03e8)^1)
 if case.startswith('native-inactive'):assert call('xw_player_sleep_native_inactive')==0
 if case=='inactive-main':assert call('xw_player_sleep_native_inactive')==-2
 callsite=0 if case=='bad-callsite' else 0x614f0 if main_word==0x102 else 0x61940 if main_word==0x703 else 0x61648 if main_word==0x202 else 0x61c5c
 start=call('xw_player_sleep_native_begin',callsite,17)
 if case in ('wrong-owner','bad-callsite','bad-image') or case.startswith('native-inactive'):
  assert start<0 and not packets and not word(symbols['test_quiesced'])
 else:
  assert start==1 and word(symbols['test_quiesced'])==1
  assert call('xw_player_sleep_native_poll')==1 and not packets
  if main_word==0x102:put(0x682cdc,0x202)
  if main_word==0x703:put(0x682cdc,0x403)
  if case=='root-changed':put(0x613e68,1)
  if case=='sequence-changed':put(0x820f7c,6)
  if case=='main-changed':put(0x682cdc,0x503)
  result=call('xw_player_sleep_native_poll')
  assert result==(0 if case in ('ready','initial-main','state-seven','inactive-main') or case.startswith('restore') else 0x1d04 if case=='ack-error' else -5),(case,result)
  assert len(packets)==int(case in ('ready','initial-main','state-seven','inactive-main','ack-error') or case.startswith('restore'))
  assert call('xw_player_sleep_native_poll')==result and len(packets)<=1
  if case.startswith('restore'):
   if case=='restore-no-begin':
    assert call('xw_player_sleep_native_restore_complete',1,17)==-7
    assert not word(symbols['test_resume_calls'])
   else:
    assert call('xw_player_sleep_native_restore_begin',0x613e60,17)==0
    put(0x613e64,15)
    if case=='restore-sequence':put(0x820f7c,5)
    if case=='restore-native-queries':put(0x820f7c,8)
    complete=call('xw_player_sleep_native_restore_complete',0 if case=='restore-rejected' else 1,17)
    if case in ('restore-sequence','restore-rejected'):
     assert complete==(-5 if case=='restore-sequence' else -3) and not word(symbols['test_resume_calls'])
    else:
     assert complete==0 and call('xw_player_sleep_native_poll')==1 and not word(symbols['test_resume_calls'])
     put(0x682cdc,0x103)
     if case=='restore-root':put(0x613e68,1)
     if case=='restore-wait':put(symbols['test_resume_wait'],1)
     if case=='restore-usb':
      put(0x613e30,1);assert call('xw_player_sleep_native_poll')==1 and not word(symbols['test_resume_calls']);put(0x613e30,0)
     resumed=call('xw_player_sleep_native_poll')
     if case=='restore-root':assert resumed==-5 and not word(symbols['test_resume_calls'])
     else:
      if case=='restore-wait':assert resumed==1;resumed=call('xw_player_sleep_native_poll')
      assert resumed==0 and word(symbols['test_resume_calls'])==1+int(case=='restore-wait')
      put(0x682cdc,0x403);assert call('xw_player_sleep_native_begin',0x61c5c,17)==1
      assert call('xw_player_sleep_native_poll')==0 and len(packets)==2
 rows.append(dict(case=case,begin=start,packets=packets,resume_calls=word(symbols['test_resume_calls'])))
report=dict(passed=True,cases=rows,device_accessed=False,native_hook_installed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_sleep_native.py','runtime/platform/player/sleep_native.h','runtime/platform/player/sleep_host.h','runtime/platform/player/sleep_retirement.h']},limits=['Native binding and original singleton/ack client instructions execute with pinned image hashes.','Loader identity, initial native state, owner, SDK/radio retirement and IPC replies are fixtures.','No patched callsites, full native event timing, RF, physical sleep or wake/rearm qualification.'])
(ROOT/'work/player-sleep-native-latest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
