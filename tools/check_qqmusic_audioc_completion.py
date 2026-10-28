"""Original AudioC power/route completion callbacks; PC-only supplied OS/hardware."""
from pathlib import Path
import io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from check_qqmusic_spider_pcm_lifecycle import raw,elf,imports,ROOT
segments=[p for p in elf.iter_segments() if p['p_type']=='PT_LOAD']
def literal(address):
    for p in segments:
        if p['p_vaddr']<=address<address+4<=p['p_vaddr']+p['p_filesz']:
            return struct.unpack_from('<I',raw,p['p_offset']+address-p['p_vaddr'])[0]
    raise AssertionError(hex(address))

def run(command,power_failure,family):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for p in segments:u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x40000);end=0x6003f000;callback=0x60018000;events=[];received=0;mute=31
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    put(literal(0x329ea4),17);put(literal(0x329eb8),23);put(literal(0x329eb4),0xffffffff)
    put(literal(0x329ec0),callback);put(literal(0x329ec4),0);put(literal(0x329ec8)+4,family)
    put(literal(0x329ee4),0);put(literal(0x329ed4),0);put(literal(0x329ed0),10)
    put(literal(0x3280c8),23);put(literal(0x3280cc),0);put(literal(0x3280d0),0)
    helpers={0x327384:'publish_volume',0x327ba8:'publish_settings',0x328134:'set_volume',0x326e68:'set_active',0x3296a0:'request_dac_event',0x337e74:'clear_dac_event',0x337ea0:'wait_dac_event',0x337dd4:'destroy_dac_event'}
    def ret(v):u.reg_write(UC_ARM_REG_R0,v&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,pc,size,context):
        nonlocal received,mute
        if pc==end:uc.emu_stop();return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if pc==0x336bcc:
            assert a[0]==17 and a[2]==4;put(a[1],command if received==0 else 0xffffffff);put(a[3],0x60007000);received+=1;ret(0)
        elif pc==0x336abc:put(a[1],0);ret(0)
        elif pc==0x337d2c:put(a[0],0x60008000);events.append('create_dac_event');ret(0)
        elif pc in helpers:events.append(helpers[pc]);ret(0)
        elif pc==callback:events.append('completion:'+str(a[0]));ret(0)
        elif imports.get(pc)=='ioctl':
            assert a[0]==23;request=a[1];value=word(a[2]);result=0
            if request==0x80046102:put(a[2],mute)
            elif request==0x40046101:mute=value&31;events.append('mute:'+str(mute))
            elif request==0x4004610d:
                assert value==(0 if command==5 else 1);events.append('power_request:'+str(value));result=-1 if power_failure else 0
            elif request in (0x40046103,0x40046105):assert value==0;events.append('route:'+hex(request))
            else:raise AssertionError(hex(request))
            ret(result)
        elif imports.get(pc) in ('pthread_mutex_lock','pthread_mutex_unlock'):ret(0)
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_ARM_REG_SP,0x6003d000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0x3297ac,0,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==end,(command,power_failure,hex(u.reg_read(UC_ARM_REG_PC)),events)
    assert received==2 and events[-1]=='completion:'+str(command==5 and 1 or 0)
    assert events.index('power_request:'+str(command==6 and 1 or 0))<len(events)-1
    if command==5:assert events.index('route:0x40046103')<len(events)-1 and events.index('publish_settings')<len(events)-1
    else:assert events.index('wait_dac_event')<events.index('power_request:1')
    return {'hardware_family_fixture':family,'command':command,'power_ioctl_failure':power_failure,'events':events,'completion_even_on_power_failure':power_failure}

def finalize(initialized,join_failure,mapped):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
    for p in segments:u.mem_write(p['p_vaddr'],p.data())
    u.mem_map(0x60000000,0x40000);end=0x6003f000;events=[]
    def put(p,v):u.mem_write(p,struct.pack('<I',v))
    put(literal(0x32bc4c),initialized);put(literal(0x32bc5c),0xffffffff)
    for i,(q,t,aux) in enumerate(((0x32bc60,0x32bc64,0x32bc68),(0x32bc6c,0x32bc70,0x32bc74),(0x32bc78,0x32bc80,0x32bc84))):
        put(literal(q),101+i);put(literal(t),201+i);put(literal(aux),301+i)
    put(literal(0x32bc7c),0x60010000 if mapped else 0);put(literal(0x32bc94),int(mapped))
    def hook(uc,pc,size,context):
        if pc==end:uc.emu_stop();return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
        if pc==0x326ea0:result=0
        elif pc==0x32959c:events.append('request_inactive')
        elif pc==0x329640:events.append('inactive_wait_boundary')
        elif pc==0x328020:events.append('mute_update')
        elif pc==0x336abc:
            payload=struct.unpack('<I',uc.mem_read(a[1],4))[0]
            assert (a[0] in (101,102) and payload==0xffffffff and a[2]==4) or (a[0]==103 and payload==30 and a[2]==16)
            events.append('exit_message:'+str(a[0]))
        elif pc==0x3375e0:
            assert a[0] in (201,202,203);events.append('join:'+str(a[0]));result=0x102 if join_failure else 0
        elif pc==0x336918:events.append('destroy_queue:'+str(a[0]))
        elif pc==0x327364:events.append('close_audio_handle')
        elif imports.get(pc)=='munmap':assert a[:2]==[0x60010000,4096];events.append('unmap_shared_volume')
        elif imports.get(pc) not in ('pthread_mutex_lock','pthread_mutex_unlock'):return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x6003d000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0x32ba94,0,count=50000)
    assert u.reg_read(UC_ARM_REG_PC)==end
    if initialized:
        assert u.reg_read(UC_ARM_REG_R0)==0
        for i in range(3):assert events.index('exit_message:'+str(101+i))<events.index('join:'+str(201+i))<events.index('destroy_queue:'+str(101+i))
        assert events.index('join:203')<events.index('close_audio_handle')
        if mapped:assert events[-1]=='unmap_shared_volume'
    else:assert u.reg_read(UC_ARM_REG_R0)==0xfffffffe and not events
    return {'initialized':initialized,'join_failure_fixture':join_failure,'mapped_volume_fixture':mapped,'events':events,'return_u32':u.reg_read(UC_ARM_REG_R0)}

if __name__=='__main__':
    rows=[run(c,f,h) for c in (5,6) for f in (False,True) for h in (0,1,2)]
    finalizers=[finalize(0,False,False),finalize(1,False,False),finalize(1,False,True),finalize(1,True,True)]
    report={'passed':True,'cases':rows,'finalizer_cases':finalizers,'physical_device_accessed':False,'limits':['Original AudioC queue-consumer/power branch/callback and mute-update instructions execute; queue delivery, DAC event completion, volume/settings work and physical ioctl effects supplied.','Completion follows the original sequencing but still fires on failed power ioctl; callback alone cannot certify hardware recovery.','Original finalizer sends three exit messages and joins before queue/handle cleanup; supplied join errors are ignored, so return0 alone is not a release certificate.','Supplied route0 and hardware-family0/1/2; other source/output routes and real hardware profile binding remain unqualified.']}
    (ROOT/'work/qqmusic-preview-audio/audioc-completion-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(rows)}))
