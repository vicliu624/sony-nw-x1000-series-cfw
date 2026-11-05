"""Replay original WLAN on/off init/select/apply; persistence/network modeled."""
import hashlib,io,json,struct,time,sys,runpy,contextlib
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
paired='--paired-callback' in sys.argv
if paired:
 with contextlib.redirect_stdout(io.StringIO()):callback=runpy.run_path(str(ROOT/'tools/test_native_wireless_callback.py'))
 section=callback['elf'].get_section_by_name('.text');u.mem_write(section['sh_addr'],section.data())
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000)
stored=0;network=2;condition=0;writes=[];events=[];navigation=[];power=[]
def hook(uc,pc,size,unused):
 if paired and pc==0xda84:
  assert uc.reg_read(UC_ARM_REG_R0) in (2,4)
  answer=0x574d0000
 elif pc==0x37f5c:
  assert uc.reg_read(UC_ARM_REG_R0)==6 and uc.reg_read(UC_ARM_REG_R1)==0x600
  uc.mem_write(uc.reg_read(UC_ARM_REG_R2),bytes([stored&255]));answer=0
 elif pc==0x38a18:
  assert uc.reg_read(UC_ARM_REG_R0)==6 and uc.reg_read(UC_ARM_REG_R1)==0x600
  value=uc.reg_read(UC_ARM_REG_R2);assert value in (0,1);writes.append(value);answer=0
 elif pc==0xb3300:answer=network
 elif pc==0x3b374:answer=condition
 elif pc==0x7461c:answer=0x5a
 elif pc==0x74608:answer=17
 elif pc==0x74668:navigation.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]);answer=0
 elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]);answer=0
 elif pc in (0xda9c,0xd4fc):power.append(hex(pc));answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(address,value=0):
 for r,v in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,value),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
 u.emu_start(address,0x50000000,count=20000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 return u.reg_read(UC_ARM_REG_R0)
initial=[]
for stored in (0,1,2,255):
 events.clear();writes.clear();navigation.clear();power.clear();call(0x88400)
 selected=struct.unpack('<I',u.mem_read(0x4ee5d8,4))[0]
 assert selected==(0 if stored==0 else 1) and not writes and not power
 assert events==[[0x20106,0,0x1d,selected]] and navigation==[[0x5a,0x9a,0,17]]
 initial.append(dict(stored_value=stored,initial_selection=selected))
cases=[]
for stored in (0,1,2,255):
 for desired in (0,1,2):
  for confirm in (False,True):
   for network in (2,3,4):
    for condition in (0,1):
     writes.clear();events.clear();power.clear()
     assert call(0x88480,desired)==0 and struct.unpack('<I',u.mem_read(0x4ee5d8,4))[0]==desired
     answer=call(0x4d8500 if paired else 0x88494,0xff0000 if confirm else 0xff0001)
     native_desired=(0 if desired==0 else 1) if paired else desired
     changed=confirm and stored in (0,1) and native_desired in (0,1) and native_desired!=stored
     assert writes==([native_desired] if changed else []) and not power
     posts=changed and ((native_desired==0 and network==2) or (native_desired==1 and (condition==1 or network!=2)))
     assert events==([[0x4c9007,0,1 if native_desired==0 else 0,0]] if posts else [])
     terminal=0x9a01 if paired and confirm else 0x5a01
     assert answer==(4 if posts else terminal)
     assert struct.unpack('<I',u.mem_read(0x4ee5d8,4))[0]==desired
     cases.append(dict(stored_value=stored,selection=desired,confirm=confirm,network_state=network,
                       native_condition=condition,writes=list(writes),posted_events=list(events),transition=hex(answer)))
report=dict(passed=True,device_accessed=False,original_arm_init_select_apply_executed=True,
            paired_callback=paired,
            initialization=initial,cases=cases,native_selection_address='0x4ee5d8',
            native_property=dict(category=6,item='0x600',on_value=0,off_value=1),
            native_change_event='0x4c9007',native_dialog_request='0x1d',
            third_selection_persisted=False,source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
            unsupported_stored_value_self_repaired=False,
            limits=['Native UI and apply instructions execute; setting store, network state and event dispatch are models.',
                    'No actual NVP write, three-mode patch, network or hardware operation.'])
out=ROOT/'work/stock-wireless-switch'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(passed=True,init_cases=len(initial),apply_cases=len(cases),on_value=0,off_value=1,third_selection_persisted=False,report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
