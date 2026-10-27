"""Continue a native first-start event into its retained Root; no Main2/2 injection."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct,sys
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];script=ROOT/'tools/check_home_client_registration.py'
previous=sys.argv
try:
 sys.argv=[str(script),'--reply-report','sources/native-home-ipc-client-registration.json','--first-start-queries','--first-start-usb-state','0']
 with contextlib.redirect_stdout(io.StringIO()):client=runpy.run_path(str(script))
finally:sys.argv=previous
u=client['u'];base=client['m'];client['hook'].__globals__['root_dispatching']=False;client['hook'].__globals__['event_phase']=False
base['call'].__globals__['intercept_actions']=False
word=lambda address:struct.unpack('<I',u.mem_read(address,4))[0]
event=base['queued'][-1].copy();assert event==[0x420017,0,0,0]
# Replay the exact native init call pair found at 11da8/11dac; do not hand-fill
# the four subsystem pointers missing from the retained registration model.
initializer_before=[word(0x66f0f0+i) for i in (0,4,8,12)]
u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
try:u.emu_start(0x11da8,0x11db0,count=50000)
except Exception as error:
 gap={'all_bounded_checks_passed':False,'scope':'Incomplete native startup dependency probe, not firmware failure','stage':'native initialization call pair 11da8/11dac','pc':hex(u.reg_read(UC_ARM_REG_PC)),'lr':hex(u.reg_read(UC_ARM_REG_LR)),'r0':hex(u.reg_read(UC_ARM_REG_R0)),'recent':client['hook'].__globals__['recent'][-24:],'Main2_2_injected':False,'error':str(error),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),script,ROOT/'tools/check_spider_restore_dispatch.py',ROOT/'work/targets-jp/SpiderApp']},'hardware_tested':False}
 (ROOT/'sources/native-first-start-root-gap.json').write_text(json.dumps(gap,indent=2)+'\n')
 print({key:gap[key] for key in ('stage','pc','lr','r0','error')});raise

assert u.reg_read(UC_ARM_REG_PC)==0x11db0
initializer_after=[word(0x66f0f0+i) for i in (0,4,8,12)]
assert all(initializer_after)

root=0x6833dc;state=bytes(u.mem_read(root,32));main=client['main_address'];main_before=bytes(u.mem_read(main,32));assert list(main_before[:2])==[3,1]
descriptor=word(word(root+4)+(state[0]-1)*4);states,columns,count,maps=struct.unpack('<4H',u.mem_read(descriptor,8));matrix,actions,mapping=[word(descriptor+i) for i in (8,12,16)]
column=next(struct.unpack('<2I',u.mem_read(mapping+i*8,8))[1] for i in range(maps) if word(mapping+i*8)==event[0]);action=word(actions+4*u.mem_read(matrix+column*states+state[1]-1,1)[0])
recent=[];requests=[];selected=[];stop=0x50000000
base['queued'].clear()
def probe(uc,pc,size,data):
 recent.append(hex(pc))
 if len(recent)>24:recent.pop(0)
 if pc==action:selected.append(hex(pc))
 if pc==0x112fc:
  requests.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]);uc.emu_stop()
u.hook_add(UC_HOOK_CODE,probe)
for register,value in ((UC_ARM_REG_R0,root),(UC_ARM_REG_R1,event[0]),(UC_ARM_REG_R2,event[2]),(UC_ARM_REG_R3,event[3]),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,stop)):u.reg_write(register,value)
try:u.emu_start(0x17c608,0,count=30000)
except Exception:
 (ROOT/'work/first-start-root-gap.json').write_text(json.dumps({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'action':hex(action),'recent':recent,'requests':requests},indent=2)+'\n');raise
assert selected==[hex(action)] and u.reg_read(UC_ARM_REG_PC) in (stop,0x112fc)
if u.reg_read(UC_ARM_REG_PC)==0x112fc:assert len(requests)==1
report={'passed':True,'extra_native_initializer_range':['0x11da8','0x11db0 exclusive'],'initializer_pointers_before':initializer_before,'initializer_pointers_after':initializer_after,'event_from_actual_first_start':event,'root_before':list(state[:2]),'main_before':list(main_before[:2]),'root_action':hex(action),'stop_pc':hex(u.reg_read(UC_ARM_REG_PC)),'coordinator_requests_not_executed':requests,'queued_after':base['queued'],'main_after':list(u.mem_read(main,2)),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),script,ROOT/'tools/check_spider_restore_dispatch.py',ROOT/'work/targets-jp/SpiderApp']},'hardware_tested':False,'limits':['Retained client/Root model, not cold boot; initial completion slots/events and extra native init call pair explicitly scheduled by the test.','No Main2/2 injected here. Coordinator request is a stop boundary, not assumed successful.','No physical display, storage, IPC or firmware execution.']}
(ROOT/'sources/native-first-start-root-continuation.json').write_text(json.dumps(report,indent=2)+'\n');print({k:report[k] for k in ('event_from_actual_first_start','root_before','main_before','root_action','stop_pc','coordinator_requests_not_executed','queued_after','main_after')})
