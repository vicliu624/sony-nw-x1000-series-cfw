"""Original Home IPC registration on preserved returned manager RAM; supplied registration packet."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
if not __debug__:raise RuntimeError('Run without Python optimization')
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--client-request-report');options=parser.parse_args()
client_source=None
if options.client_request_report:
    from evidence_checks import verify_report
    client_source=(ROOT/options.client_request_report).resolve();assert client_source.is_relative_to(ROOT/'sources')
    client_request=verify_report(ROOT,options.client_request_report)
base=ROOT/'tools/check_saved_manager_arguments.py'
with contextlib.redirect_stdout(io.StringIO()):
    m=runpy.run_path(str(base),init_globals={'return_report':'sources/native-ipc-manager-return.json','output_report':'sources/native-ipc-saved-manager-arguments.json'})
u=m['manager'];u.hook_del(m['manager_hook_id'])
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
core,ipc,request=0x60000000,0x60006000,0x6001b000
assert word(core+0x51b4)==0xf298 and word(core+0x51bc)==0xf314
assert word(ipc+24)==0 and word(ipc+40)==0
symbols={s.name:s['st_value'] for s in m['elf'].get_section_by_name('.dynsym').iter_symbols()}
replies=[];queued=[];frames=[];recent=[];empty=False;checkpoints=[]

def hook(uc,pc,size,data):
    global empty
    a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    recent.append(hex(pc))
    if len(recent)>24:recent.pop(0)
    if pc==symbols['memcpy']:
        assert a[2]<=0x10000;uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
    if pc in (0xf650,0xf664,0xf694,0xf6a8,0xf6c4):checkpoints.append({'pc':hex(pc),'r0':hex(a[0]),'node':hex(word(ipc+24)),'pool':word(ipc+40)});return
    if pc==0x16d18:
        payload=bytes(uc.mem_read(a[2],a[3]))
        if a[1]==864:replies.append(payload)
        else:
            assert a[:2]==[44,865];frames.append(payload)
    elif pc==0x1967c:
        assert a[0]==77 and a[2:]==[52,0];queued.append(bytes(uc.mem_read(a[1],52)))
    elif pc==0x1978c:
        assert a[0]==77 and a[2:]==[52,0]
        if not queued:empty=True;uc.emu_stop();return
        uc.mem_write(a[1],queued.pop(0))
    elif pc not in (0x1a4f0,0x1a508,0x1a458,0xa188,0x1c4d0):return
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
manager_hook_id=u.hook_add(UC_HOOK_CODE,hook)

def call(entry,args):
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
    u.reg_write(UC_ARM_REG_SP,0x6001f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    try:u.emu_start(entry,0x50000000,count=50000)
    except Exception:
        (ROOT/'work/home-ipc-registration-gap.json').write_text(json.dumps({'pc':hex(u.reg_read(UC_ARM_REG_PC)),'recent':recent,'scope':'Offline model gap, no device operation'},indent=2)+'\n');raise

packet=list(struct.unpack('<8I',bytes.fromhex(client_request['request_hex']))) if client_source else [32,0,0,0,864,865,432,0x10010001]
assert packet==[32,0,0,0,864,865,432,0x10010001]
u.mem_write(request,struct.pack('<8I',*packet));call(0xf584,(ipc,request))
assert u.reg_read(UC_ARM_REG_PC)==0x50000000
reply=list(struct.unpack('<5I',replies[0]));assert reply==[20,0,0,0,1],reply
assert word(ipc+24)==0 and word(ipc+40)==0
assert any(c['pc']=='0xf6a8' and c['r0']=='0x102' for c in checkpoints)
active_reregistration={'internal_registration_status':'0x102','reply':reply,'pool_used_after':0,'port_entries_after':[],'checkpoints':checkpoints.copy()}
# Positive registration requires state0. This is an explicit prerequisite fixture,
# not a state transition established by the returned manager replay.
u.mem_write(0x60010000+12,struct.pack('<I',0));replies.clear();checkpoints.clear()
call(0xf584,(ipc,request));assert u.reg_read(UC_ARM_REG_PC)==0x50000000
assert list(struct.unpack('<5I',replies[0]))==[20,0,0,0,1]
node=word(ipc+24)
assert ipc+48<=node<ipc+432, {'node':hex(node),'pool_used':word(ipc+40),'replies':[p.hex() for p in replies],'queued':[p.hex() for p in queued],'checkpoints':checkpoints}
assert [word(node+i) for i in (0,4,8)]==[0,1,865] and word(ipc+40)==1
registration_queue=[list(struct.unpack('<5I',p[:20])) for p in queued]
assert registration_queue==[[0xffffffff,0,9,1,1],[1,0,5,0,0]]
call(0xf0fc,(ipc,))
assert empty and [list(struct.unpack('<5I',p)) for p in frames]==[[20,0,9,1,1],[20,0,5,0,0]]
paths=[Path(__file__),base,*m['paths']]+([client_source] if client_source else [])
report={'all_bounded_checks_passed':True,'already_active_reregistration_control':active_reregistration,'positive_home_state0_fixture':True,'registration_request_fixture':packet,'registration_reply':reply,'resolved_existing_home_id':1,
        'port_node':hex(node),'pool_used':word(ipc+40),'port_registry':[[1,865]],'registration_queue_prefixes':registration_queue,
        'activation_enqueued_by_native_registration':True,'notification_hex':frames[-1].hex(),'all_frames_hex':[p.hex() for p in frames],'destination_port':865,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'limits':['Preserved returned manager RAM with native IPC constructor and empty port pool; original f584 registration, existing PID lookup, native pool/list insertion and f314/f0fc framing execute.',
                  'Home PID432/registration packet supplied. Positive probe changes Home record state2 to0 explicitly; not a proven native startup transition. Already-active re-registration separately rejected internally0x102 and cleans temporary slot.',
                  'Post-return re-registration is a bounded probe, not a claim that stock Home registers at this point.',
                  'All registration broadcasts framed without deletion or explicit activation injection; libc memcpy, queue/locks/socket send virtual. No physical device access.']}
if client_source:
    report['original_client_request_input']=options.client_request_report
    report['limits'].append('Registration bytes captured from original SpiderApp constructor/registration; PID/OS handles and Home state0 prerequisite still supplied.')
(ROOT/('sources/native-home-ipc-client-registration.json' if client_source else 'sources/native-home-ipc-registration.json')).write_text(json.dumps(report,indent=2)+'\n')
print('Original Home registration resolves PID432 to app1, allocates port865 and frames activation')
