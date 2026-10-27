"""Warm Main cycles with original manager replies, retaining the initial-state limitation."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct,sys
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC
from native_lookup_fixture import request_in_session
ROOT=Path(__file__).resolve().parents[1];client_source=ROOT/'tools/check_home_client_registration.py'
previous=sys.argv
try:
 sys.argv=[str(client_source),'--reply-report','sources/native-home-ipc-client-registration.json','--acknowledge-activation']
 with contextlib.redirect_stdout(io.StringIO()):seed=runpy.run_path(str(client_source))
finally:sys.argv=previous
with contextlib.redirect_stdout(io.StringIO()):primitives=runpy.run_path(str(ROOT/'tools/check_main_activation_ack.py'))
u=primitives['machine']();call=primitives['call'];ret=primitives['returned'];manager_session=seed['lookup_session'];manager=manager_session['emulator']
ctx=0x820f68;main=seed['main_address'];u.mem_write(ctx,bytes(seed['u'].mem_read(ctx,0x1b4)));u.mem_write(main,bytes(seed['u'].mem_read(main,32)))
assert list(u.mem_read(main,2))==[3,4]
word=lambda uc,address:struct.unpack('<I',uc.mem_read(address,4))[0]
assert word(u,ctx+4)==2 and word(manager,0x60010000+12)==2
pending=None;requests=[];transitions=[]
def hook(uc,pc,size,data):
 global pending
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==0x268c9c:
  assert a[:2]==[500,55] and a[3]==24 and pending is None
  packet=bytes(uc.mem_read(a[2],24));words=list(struct.unpack('<6I',packet));assert words[0]==24 and words[2:5]==[1,1,864]
  details={};pending,_=request_in_session(manager_session,packet,details=details)
  reply=list(struct.unpack('<4I',pending));assert reply[:3]==[16,words[1],1]
  requests.append({'request':words,'reply':reply,'client_state_at_send':word(uc,ctx+4),'manager_home_after':word(manager,0x60010000+12),'manager_details':details})
 elif pc==0x268d48:
  assert a[0]==500 and a[2]==16 and pending is not None;uc.mem_write(a[1],pending);uc.mem_write(a[3],struct.pack('<I',len(pending)));pending=None
 elif pc not in (0x337a80,0x337ae8,0xb00bc,0x265298,0x17c42c,0x33b918,0x33b83c):return
 ret(uc)
u.hook_add(UC_HOOK_CODE,hook)
for cycle in range(3):
 for event,expected,client_state in ((0x41000a,[2,2],1),(0x410009,[3,4],2)):
  assert call(u,0x17c608,(main,event,0,0))==0
  state=list(u.mem_read(main,2));assert state==expected and word(u,ctx+4)==client_state and requests[-1]['reply'][3]==0,(cycle,event,state,requests[-1])
  assert word(manager,0x60010000+12)==client_state
  transitions.append({'cycle':cycle+1,'completion_event_supplied':hex(event),'main_after':state,'client_after':client_state,'manager_home_after':word(manager,0x60010000+12)})
assert pending is None and len(requests)==6
home_before=bytes(manager.mem_read(0x60010000,64));bad=bytearray(struct.pack('<6I',*requests[-1]['request']));struct.pack_into('<I',bad,8,0x3ffff)
rejected,_=request_in_session(manager_session,bytes(bad));rejected_words=list(struct.unpack('<4I',rejected));assert rejected_words[3]!=0 and bytes(manager.mem_read(0x60010000,64))==home_before,rejected_words

tracked=[Path(__file__),client_source,ROOT/'tools/check_main_activation_ack.py',ROOT/'tools/native_lookup_fixture.py',ROOT/'sources/native-home-client-registration-active.json',ROOT/'work/targets-jp/SpiderApp',ROOT/'work/targets-jp/sysmgrd']
report={'passed':True,'initial_warm_state':[3,4],'initial_seed_limit':'Seed uses existing Main2/2 activation prerequisite; native acknowledgement produces initial3/4. This is not cold boot.','invalid_app_control':{'app_id':'0x3ffff','reply':rejected_words,'home_record_unchanged':True},'cycles':transitions,'requests':requests,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['Completion events supplied; preceding GUI workers and real departure/return not executed.','Original client and retained original manager process every reply; not forced success packets.','Initial warm-state prerequisite remains; no real IPC, kernel or rendering qualification.']}
(ROOT/'sources/native-main-warm-manager-cycles.json').write_text(json.dumps(report,indent=2)+'\n');print('Three warm Main/client cycles accepted by the same original manager; initial-state/completion-event fixtures remain.')
