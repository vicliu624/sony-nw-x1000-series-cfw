"""Compiled correlation hook, original release and full RX/TX code budget."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
OUT=ROOT/'work/espnow-completion-hook';OUT.mkdir(exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):env=runpy.run_path(str(ROOT/'tools/test_radio_full_tx.py'))
cpu,put,word,call,free_count,command=[env[n] for n in ('cpu','put','word','call','free_count','command')]
sources=['runtime/platform/espnow/'+n for n in ('radio_packet.c','radio_full_rx.c','radio_full_tx.c','radio_tx_completion.c','radio_completion_hook.S','radio_word_command.c','radio_command_hook.S')]
elf=OUT/'completion.elf';link=OUT/'completion.ld';link.write_text(env['link'].read_text())
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-mthumb','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(link),*sources,'-o',str(elf)],cwd=ROOT,check=True)
with elf.open('rb') as f:
 e=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']];symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
cpu.mem_write(0xc000a190,bytes(1900))
for a,d in sections:cpu.mem_write(a,d)
cpu.ctl_remove_cache(0xc000a190,0xc000a8fc)
state=symbols['xnow_full_tx'];completion=symbols['xnow_tx_completion']
cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
# Hook the common wrapper rather than only task3's call site.
original=bytes(cpu.mem_read(0xd51c,8));assert original==bytes.fromhex('80b5f3f720ef80bd')
cpu.mem_write(0xd51c,struct.pack('<HHI',0x4b00,0x4718,symbols['xnow_radio_completion_entry']|1))
cpu.ctl_remove_cache(0xd51c,0xd524)
seq=100;releases=[]
def stop(u,pc,size,unused):
 if pc==0x1360:
  packet=u.reg_read(UC_ARM_REG_R0)
  if word(completion)==packet:assert word(completion+8)!=word(completion+4),'published completion before original free'
  releases.append(packet)
 if pc==0x3a16:u.emu_stop()
cpu.hook_add(UC_HOOK_CODE,stop)
def operation(kind):
 global seq
 command(state+16,kind);seq+=1;command(state+4,seq)
 assert word(state+8)==seq
 return struct.unpack('<i',cpu.mem_read(state+12,4))[0]
def submit():
 assert operation(1)==0
 packet=word(state+24);cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11))
 command(state+20,15);command(state+32,0x88776602);command(state+36,0xaa99)
 assert operation(2)==0 and word(completion)==packet and word(completion+4)==seq
 return packet,seq
def finish(packet,status,raw):
 regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7);values=(packet,0x5555,0x6666,0x7777)
 for reg,value in zip(regs,values):cpu.reg_write(reg,value)
 cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
 put(0x208008,status);put(0x20800c,raw);put(0xc0008a08,7)
 before=len(releases);cpu.emu_start(0x3a0d,0x3a18,count=30000)
 assert cpu.reg_read(UC_ARM_REG_PC)==0x3a16 and cpu.reg_read(UC_ARM_REG_SP)==0x208000
 assert cpu.reg_read(UC_ARM_REG_R0)==7 and cpu.reg_read(UC_ARM_REG_R1)==0xc0008a08
 assert tuple(cpu.reg_read(reg) for reg in regs)==values
 assert releases[before:]==[packet]
env['env']['queue_result'][0]=0
for status in (0,1):
 packet,token=submit();assert operation(1)==-2
 other=call(0xd458,1900);finish(other,1,0xffffffff)
 assert word(completion)==packet and word(completion+8)==word(completion+20)
 finish(packet,status,0x00070302)
 assert word(completion)==0 and word(completion+8)==token and word(completion+12)==status and word(completion+16)==0x00070302
 assert free_count()==3 and operation(1)==-2
 command(completion+20,token)
# Original task5 can reject before any MAC completion exists; common free
# still publishes the correlated terminal result and returns original0.
packet,token=submit();before=len(releases)
assert call(0xd51c,packet)==0
assert releases[before:]==[packet] and free_count()==3
assert word(completion)==0 and word(completion+8)==token and word(completion+12)==2 and word(completion+16)==0
command(completion+20,token)
# Rejected submission clears correlation and is freed only by d800.
assert operation(1)==0;packet=word(state+24);cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11));command(state+20,15)
env['env']['queue_result'][0]=1
before=len(releases);assert operation(2)==-1 and word(completion)==0 and releases[before:]==[packet] and free_count()==3
assert operation(1)==0 and operation(3)==0 and free_count()==3
report={'passed':True,'original_common_management_free_patched':True,'pre_mac_rejection_reports_terminal_status2':True,'original_release_exactly_once':True,'unrelated_management_packet_ignored_by_observer':True,'completion_status_and_token_correlated':True,'unread_completion_backpressure':True,'queue_rejection_clears_pending':True,'task_stack_callee_saved_and_displaced_loads_preserved':True,'combined_reserved_bytes':sum(len(d) for _,d in sections),'completion_records_and_scheduler_modeled':True,'device_accessed':False,'download_image_created':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'tools/test_radio_completion_hook.py']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


