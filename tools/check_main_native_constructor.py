"""Inspect original Main constructor state without supplying a Main context."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'tools/check_spider_restore_dispatch.py'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute-first-activation',action='store_true');options=parser.parse_args()
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(base))
u=m['u'];call=m['call'];call.__globals__['intercept_actions']=False;call.__globals__['deactivate_probe']=False
recent=[];services=[];inactive_probe=False;first_activation_probe=False;selected=[];first_body=False;query8_fixture=0;battery_fixture=0;first_services=[];native_constructor_calls=[]
def hook(uc,pc,size,data):
    recent.append(hex(pc))
    if len(recent)>32:recent.pop(0)
    if first_body and pc==0x61320:native_constructor_calls.append(hex(pc));return
    if first_body and pc in (0xb05e8,0xb0764,0xb0bdc):
        value=query8_fixture if pc==0xb0764 else battery_fixture
        first_services.append({'entry':hex(pc),'value_fixture':value if pc!=0xb05e8 else None})
        if pc!=0xb05e8:uc.mem_write(uc.reg_read(UC_ARM_REG_R0),struct.pack('<I',value))
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if first_activation_probe and pc==0x61414:selected.append(hex(pc));uc.emu_stop();return
    if inactive_probe and pc==0xb0664:
        services.append({'entry':'0xb0664','inactive_ack_helper_virtual':True});uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc not in (0x17c42c,0x33b918,0x33b83c):return
    services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
try:result=call(0x61320,())
except Exception:
    (ROOT/'work/main-constructor-gap.json').write_text(json.dumps({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'recent':recent},indent=2)+'\n');raise
assert result==0
pointer=struct.unpack('<I',u.mem_read(0x682cd8,4))[0];assert pointer==0x682cdc
context=bytes(u.mem_read(pointer,32));assert list(context[:2])==[3,1];assert context[13]==6 and struct.unpack_from('<I',context,4)[0]==0x3ef680
word=lambda address:struct.unpack('<I',u.mem_read(address,4))[0]
descriptor=word(word(pointer+4)+(context[0]-1)*4)
state_count,event_columns,action_count,map_count=struct.unpack('<4H',u.mem_read(descriptor,8))
assert state_count==7 and map_count==27 and u.mem_read(descriptor+28,1)[0]==0
matrix,actions,event_map=[word(descriptor+offset) for offset in (8,12,16)]
routes=[]
for index in range(map_count):
    event,column=struct.unpack('<2I',u.mem_read(event_map+index*8,8))
    action_index=u.mem_read(matrix+column*state_count+context[1]-1,1)[0]
    assert column<event_columns and action_index<action_count
    routes.append({'event':hex(event),'action':hex(word(actions+4*action_index))})
assert next(v['action'] for v in routes if v['event']=='0x410009')=='0x613cc'
assert call(0x17c608,(pointer,0x410009,0,0))==0
assert list(u.mem_read(pointer,2))==[3,1]
inactive_probe=True
assert call(0x17c608,(pointer,0x41000a,0,0))==0
assert list(u.mem_read(pointer,2))==[2,1]
inactive_probe=False;first_activation_probe=True
for register,value in ((UC_ARM_REG_R0,pointer),(UC_ARM_REG_R1,0x410009),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x60008000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(register,value)
u.emu_start(0x17c608,0x50000000,count=20000)
assert u.reg_read(UC_ARM_REG_PC)==0x61414 and selected==['0x61414']
first_cases=[]
if options.execute_first_activation:
    first_activation_probe=False
    for query8_fixture,battery_fixture in ((0,0),(0,1),(1,0),(1,1)):
        first_body=False;assert call(0x61320,())==0
        inactive_probe=True;assert call(0x17c608,(pointer,0x41000a,0,0))==0;inactive_probe=False
        assert list(u.mem_read(pointer,2))==[2,1]
        first_body=True;first_services.clear();native_constructor_calls.clear();m['queued'].clear()
        assert call(0x17c608,(pointer,0x410009,0,0))==0
        assert list(u.mem_read(pointer,2))==[3,1] and native_constructor_calls==['0x61320']
        expected_event=0x42001a if query8_fixture else 0x420017 if not battery_fixture else None
        assert m['queued']==([[expected_event,0,0,0]] if expected_event else []),m['queued']
        assert [v['entry'] for v in first_services]==(['0xb05e8','0xb0764'] if query8_fixture else ['0xb05e8','0xb0764','0xb0bdc'])
        first_cases.append({'query_operation8_value_fixture':query8_fixture,'battery_value_fixture':battery_fixture,'native_constructor_calls':native_constructor_calls.copy(),'services_virtual':first_services.copy(),'main_after':[3,1],'queued':[v.copy() for v in m['queued']]})
    first_body=False
report={'all_bounded_checks_passed':True,'constructor':'0x61320','context':hex(pointer),'native_mode_state':list(context[:2]),'context_byte13':context[13],'descriptor':'0x3ef680','context_hex':context.hex(),'initial_event_routes':routes,'activation_completion_in_constructor_state':{'event':'0x410009','native_action':'0x613cc','mode_state_after':[3,1],'no_activation_request':True},'initial_inactive_completion_probe':{'event_fixture':'0x41000a','mode_state_after':[2,1],'inactive_ack_helper_virtual':'0xb0664'},'first_activation_selection':{'event_fixture':'0x410009','action':'0x61414','body_executed':False,'differs_from_resume_action':'0x614b0'},'services_virtual':services,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),base,ROOT/'work/targets-jp/SpiderApp')},
        'limits':['Original constructor61320 and generic state constructor17c56c/17c494 execute; context bytes not supplied.',
                  'No full startup/registration or transition to Main2/2 established. Inactive completion event supplied, inactive-ack helper virtual; subsequent first-start activation stops at61414 before body. Logging virtual. No device execution.']}
if options.execute_first_activation:
    report['first_activation_body_cases']=first_cases;report['first_activation_body_executed']=True
    report['limits']=[line.replace('subsequent first-start activation stops at61414 before body.','initial selection probe stops at61414; separate branch probes execute its body with helper boundaries.') for line in report['limits']]
    report['limits'].append('Original61414 body executed in four independent constructor/reset probes. It reconstructs Main, calls virtual active-ack/query8/battery helpers, and returns3/1. Event41000a prerequisite and helper results supplied; no actual query replies or full boot established. First-start results do not establish recovery Main2/2.')
(ROOT/('sources/native-main-first-activation.json' if options.execute_first_activation else 'sources/native-main-constructor.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Original Main constructor:',report['native_mode_state'],hex(pointer))
