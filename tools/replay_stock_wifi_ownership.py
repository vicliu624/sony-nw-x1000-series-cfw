"""Read-only bounded original NetFront/daemon CPU replay. No kernel IPC/radio.
All app-manager and connection-manager imports are explicit RAM models.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-wifi-research';net=(work/'netfront').read_bytes();daemon=(ROOT/'work/qqmusic-wifi/cnmgr_daemon').read_bytes()
def machine(raw):
 elf=ELFFile(io.BytesIO(raw));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD'];lo=min(s['p_vaddr'] for s in segments)&~4095;hi=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(lo,hi-lo)
 for s in segments:u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x40000);return u
rows=[]
# Original browser UI producer -> request context -> main-loop exit dispatch.
u=machine(net);events=[];ui_closes=[];end=0x2000100;request=0x2001000;u.mem_write(request,bytes(24))
def browser_hook(uc,pc,size,unused):
 if pc==end:uc.emu_stop();return
 result=0
 if pc==0xafac:result=request
 elif pc in (0x99208,0x91544):pass  # UI registry/log and zero child-count fixture
 elif pc==0x905e8:ui_closes.append('UI close requested')
 elif pc==0x3349a4:result=0x2002000
 elif pc==0x33767c:
  target=uc.reg_read(UC_ARM_REG_R1);vector=uc.reg_read(UC_ARM_REG_R2);mode=uc.reg_read(UC_ARM_REG_R3);pointer,terminator=struct.unpack('<2I',uc.mem_read(vector,8));argument=bytes(uc.mem_read(pointer,32)).split(b'\0')[0].decode()
  assert (target,mode,argument,terminator)==(1,1,'--WifiCon',0);events.append({'target':target,'mode':mode,'argument':argument})
 elif pc not in (0x2fc81c,0x2fc85c,0xa9e8):return
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,browser_hook)
ui=0x2003000;ui_object=0x2003100;ui_event=0x2003300
u.mem_write(ui,struct.pack('<I',ui_object));u.mem_write(ui_event+28,struct.pack('<I',1))
for register,value in ((UC_ARM_REG_R0,ui),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,ui_event),(UC_ARM_REG_SP,0x203f000),(UC_ARM_REG_LR,end)):u.reg_write(register,value)
u.emu_start(0x90774,end,count=3000);assert u.reg_read(UC_ARM_REG_PC)==end
assert struct.unpack('<I',u.mem_read(request,4))[0]==3 and not events and ui_closes==['UI close requested']
for arguments in ((0,1,0),):
 for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),arguments):u.reg_write(register,value)
 u.reg_write(UC_ARM_REG_SP,0x203f000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0x2fb3e8,end,count=3000);assert u.reg_read(UC_ARM_REG_PC)==end
 if arguments[0]==3:assert struct.unpack('<I',u.mem_read(request,4))[0]==3 and not events
assert events
# Init and fin mutate the SAME daemon object's global reference counter.
counter=[]
for entry,initial,expected,stop_at in [(0xc2a0,1,2,0xbd7c),(0xc2cc,2,1,0xc2e0),(0xc2cc,1,0,0xc2e0)]:
 u=machine(daemon);obj=0x2001000;u.mem_write(obj+0x13254,struct.pack('<I',initial));u.reg_write(UC_ARM_REG_R6,obj)
 def stop(uc,pc,size,unused):
  if pc==stop_at:uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,stop);u.emu_start(entry,stop_at,count=50);actual=struct.unpack('<I',u.mem_read(obj+0x13254,4))[0];assert actual==expected
 counter.append({'entry':hex(entry),'initial':initial,'final':actual,'stop_before':hex(stop_at)})
report={'passed':True,'source_hashes':{'netfront':hashlib.sha256(net).hexdigest(),'cnmgr_daemon':hashlib.sha256(daemon).hexdigest()},'browser_callback':'0x2fb3e8','ui_producer':'0x90774','supplied_ui_event_payload':1,'ui_child_count_fixture':0,'ui_close_boundary':ui_closes,'supplied_callback_tuples':[[0,1,0]],'context_mode_written_by_original_code':3,'browser_network_request':events,'daemon_global_reference_counter_offset':'0x13254','counter_cases':counter,'physical_device_accessed':False,'network_or_ipc_executed':False,'limits':['Original UI producer now generates category3 callback/context write; UI event input, zero child count and UI close boundary modeled.','Main-loop cleanup is not executed; its final callback(0,1,0) is supplied after producer. UI registration eligibility and full return/resume remain unproven.','App change target/mode/argv are original bytes; actual manager IPC is modeled.','Counter mutation proven; automatic power-down consequence and cause of reported IP loss not established.','Not permission or qualification to call original Wi-Fi control from an external app.']}
(ROOT/'sources/qqmusic-stock-wifi-ownership.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
