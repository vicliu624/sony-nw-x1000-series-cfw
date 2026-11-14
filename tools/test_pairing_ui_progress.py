"""Actual ARM GUI tick with modeled native event/renderer and pairing state."""
import argparse
import io
import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP
from review_managed_remote_profile import digest, receipt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--host-review', required=True)
args = p.parse_args()
path, review = receipt(args.host_review)
library = path.parent / 'libx1000-player-analysis.so'
assert digest(library) == review['library_sha256']
elf = ELFFile(io.BytesIO(library.read_bytes()))
syms = {s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']!='STT_FILE'}
bss = elf.get_section_by_name('.bss')
origin = ''
local = {}
for symbol in elf.get_section_by_name('.symtab').iter_symbols():
    if symbol['st_info']['type']=='STT_FILE':origin=symbol.name
    elif origin=='remote_page_adapter.c' and symbol.name in ('page','view'):
        assert bss['sh_addr']<=symbol['st_value']<bss['sh_addr']+bss['sh_size']
        local[symbol.name]=symbol['st_value']
    elif origin=='remote_auto.c' and symbol.name=='factory':
        local['factory']=symbol['st_value']
assert set(local)=={'page','view','factory'}
syms.update(local)
dis = subprocess.check_output(['arm-linux-gnueabi-objdump','-d','--disassemble=xw_player_host_remote_page_tick',str(library)],text=True)
pthread = int(re.search(r'\b([0-9a-f]+) <pthread_self@plt>',dis)[1],16)
dispatch_dis = subprocess.check_output(['arm-linux-gnueabi-objdump','-d','--disassemble=xw_host_pid_dispatch',str(library)],text=True)
errno_plt = int(re.search(r'\b([0-9a-f]+) <__errno_location@plt>',dispatch_dis)[1],16)
native_review = json.loads((path.parent/'remote-page/report.json').read_text())
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pairing-ui-layout-',dir=root/'work') as folder:
    c=Path(folder)/'layout.c';obj=Path(folder)/'layout.o'
    c.write_text(('#define WR_PAIRING_TRACE\n' if 'wr_start_failure_capture' in syms else '') +
                 '#define WR_PAIRING_PROCESS\n#include <stddef.h>\n'
                 '#include "runtime/apps/wireless-remote/settings_factory.h"\n'
                 'char backend_generation_offset[offsetof(struct wr_settings_backend,generation)+1];\n'
                 'char factory_initialized_offset[offsetof(struct wr_settings_factory,initialized)+1];\n'
                 'char factory_owner_offset[offsetof(struct wr_settings_factory,pairing.owner)+1];\n')
    with c.open('a') as append:
        append.write('char backend_owner_offset[offsetof(struct wr_settings_backend,owner)+1];\n'
                     'char backend_phase_offset[offsetof(struct wr_settings_backend,phase)+1];\n')
    subprocess.run(['arm-linux-gnueabi-gcc','-c','-I',str(root),str(c),'-o',str(obj)],check=True)
    layout=ELFFile(io.BytesIO(obj.read_bytes()))
    generation_offset,=(s['st_size']-1 for s in layout.get_section_by_name('.symtab').iter_symbols()
                        if s.name=='backend_generation_offset')
    initialized_offset,=(s['st_size']-1 for s in layout.get_section_by_name('.symtab').iter_symbols()
                          if s.name=='factory_initialized_offset')
    owner_offset,=(s['st_size']-1 for s in layout.get_section_by_name('.symtab').iter_symbols()
                    if s.name=='factory_owner_offset')
    backend_offsets={s.name:s['st_size']-1 for s in layout.get_section_by_name('.symtab').iter_symbols()
                     if s.name in ('backend_owner_offset','backend_phase_offset')}
native_file = root/native_review['artifact']
assert digest(native_file)==native_review['sha256']
native_elf = ELFFile(io.BytesIO(native_file.read_bytes()))
cases = {}
for case in ('searching','found','approval','verified','saved','failed','timeout','wrong-page',
             'wrong-owner','closing','popup-close-retry','reentrant','starting-real',
             'starting-timeout-real','exited-real','native-found','native-saved',
             'pair-dialog-show','pair-dialog-yes','pair-dialog-no','pair-dialog-expired','native-pair-yes','native-pair-no'):
    base, area, stop = 0x50000000, 0x70000000, 0x7000ff00
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    cpu.mem_map(base,0x100000);cpu.mem_map(area,0x10000)
    integrated=case.startswith('native-')
    if integrated:
        cpu.mem_map(0x8000,0x1000000)
        for seg in native_elf.iter_segments():
            if seg['p_type']=='PT_LOAD':cpu.mem_write(seg['p_vaddr'],seg.data())
        master=int(native_review['metadata_address'],16)
        def word(a):return struct.unpack('<I',cpu.mem_read(a,4))[0]
        initializers=word(word(master+192*4)+20)
        startup=word(initializers) if initializers else 0
    else:
        cpu.mem_map(0xa5000,4096);cpu.mem_map(0x17c000,4096)
        cpu.mem_map(0x4ec000,4096)
    for seg in elf.iter_segments():
        if seg['p_type']=='PT_LOAD':cpu.mem_write(base+seg['p_vaddr'],seg.data())
    if integrated:
        for name,value in (('host_ready',1),('host_busy',0),('host_owner',17)):
            cpu.mem_write(base+syms[name],struct.pack('<I',value))
    if case in ('starting-real','starting-timeout-real','exited-real'):
        cpu.mem_write(base+syms['factory']+initialized_offset,struct.pack('<I',1))
        cpu.mem_write(base+syms['factory']+owner_offset,struct.pack('<I',0 if case=='exited-real' else 123))
    cpu.mem_write(base+syms['page'],struct.pack('<IIQII',area+0x100,17,41,1,2))
    cpu.mem_write(area+0x100+generation_offset,struct.pack('<Q',41))
    cpu.mem_write(area+0x100+backend_offsets['backend_owner_offset'],struct.pack('<I',17))
    cpu.mem_write(area+0x100+backend_offsets['backend_phase_offset'],struct.pack('<I',1))
    cpu.mem_write(base+syms['view'],struct.pack('<10I',0x63bd8c,0x754ac4,17,13900,2,1,case=='closing',1,0,13901))
    for name in ('pairing_waiting','pairing_wait_dialog'):
        cpu.mem_write(base+syms[name],struct.pack('<I',1))
    # Keep passive binding refresh settled; it is independently exercised by
    # test_remote_binding_menu, rather than adding unrelated renderer events.
    cpu.mem_write(base+syms['binding_display_state'],struct.pack('<I',1))
    pair_dialog=case.startswith('pair-dialog-')
    sid=0x4eb99c+43*48+4;cpu.mem_write(sid,struct.pack('<I',14400))
    if pair_dialog:
        cpu.mem_write(base+syms['pairing_waiting'],struct.pack('<I',0))
        cpu.mem_write(base+syms['pairing_peer_open'],struct.pack('<I',1))
    if case=='reentrant':cpu.mem_write(base+syms['pairing_advancing'],struct.pack('<I',1))
    state=[0x0202 if case=='wrong-page' else 0xc202]
    if pair_dialog:state[0]=0x9b02
    progress={'searching':20,'approval':22,'verified':23,'saved':24,'failed':25}.get(case,21)
    if case=='native-saved':progress=24
    if case=='timeout':progress=20
    native_live=not integrated
    posts=[];commits=[];cancels=[];events=[];traces=[]
    selections=[]
    audit=[]
    def hook(u,pc,size,unused):
        registers=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        if integrated and native_live:
            for name in ('getpid','xw_host_pid_dispatch','xw_player_host_remote_page_request','xw_player_host_remote_pairing_begin','xw_player_remote_page_caller'):
                if pc==base+syms[name]:audit.append((name,registers,hex(u.reg_read(UC_ARM_REG_LR))))
            if pc==0xda84:audit.append(('native-request',registers,hex(u.reg_read(UC_ARM_REG_LR))))
        if pc==base+pthread:result=18 if case=='wrong-owner' else 17
        elif pc in (base+syms['xw_player_remote_page_image_valid'],base+syms['xw_player_remote_view_image_valid']):result=1
        elif pc==base+syms['wr_view_menu_context']:result=0x683400
        elif pc==base+syms['wr_view_menu_state']:
            result=(cpu.mem_read(0x683400,1)[0]<<8)|cpu.mem_read(0x683401,1)[0] if integrated else state[0]
        elif pc==base+syms['wr_native_choice_view_observe']:result=-4
        elif pc==base+syms['wr_view_pair_resource_ready']:result=1
        elif pc==base+syms['xw_player_host_remote_pairing_select']:selections.append(True);result=1
        elif pc==base+syms['xw_player_host_remote_binding_peek']:
            # This fixture supplies discovery state. Actual persisted binding,
            # lookup errors and deletion are exercised by test_remote_binding_menu.
            result=1
        elif pc==base+syms['xw_player_host_remote_pairing_progress'] and case not in ('starting-real','starting-timeout-real','exited-real'):result=progress
        elif pc==base+syms['xw_player_host_original_exiting']:result=0
        elif pc==base+syms['hb_monotonic_millis']:
            u.mem_write(registers[0],struct.pack('<Q',16000 if case in ('timeout','starting-timeout-real') else 3500 if case=='starting-real' else 500));result=0
        elif pc==base+syms['xw_player_host_remote_pairing_begin']:
            if not integrated:commits.append(True)
            result=3 if integrated else 1
        elif pc==base+syms['xw_player_host_remote_pairing_display_peer']:
            u.mem_write(registers[0],bytes.fromhex('021122334455'));result=0
        elif pc==base+syms['xw_player_host_remote_pairing_cancel']:cancels.append(True);result=0
        elif pc==base+syms['xw_player_pairing_trace_radio']:traces.append(registers[:2]);result=0
        elif pc==0xa57f0:
            posts.append(registers);result=0 if case=='popup-close-retry' else 1
        elif integrated and pc==0xda84:
            if not native_live:
                result=0x57530002 if registers[0] in (1,2) else 0x57520000
                u.reg_write(UC_ARM_REG_R0,result);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
            if u.reg_read(UC_ARM_REG_LR) in native_review['request_callers']:
                u.reg_write(UC_ARM_REG_PC,base+syms['getpid']);return
            result=1234
        elif integrated and pc==base+errno_plt:result=area+0x300
        elif integrated and pc in (startup,0x17c42c,0x33b918,0x88654):
            if pc==0x88654:
                assert list(u.mem_read(0x683400,2))==[155,1], 'MAC initializer must observe its own menu group'
            result=0
        elif pc==0x17c608:
            if integrated and not native_live:return
            if integrated and registers[1]!=0x4a0119:return
            assert registers==[0x683400,0x4a0119,0xff0000,0]
            events.append(registers)
            if integrated:return
            state[0]=0x9b01;result=0
        else:return
        u.reg_write(UC_ARM_REG_R0,result&0xffffffff);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    cpu.hook_add(UC_HOOK_CODE,hook)
    def invalid(u,access,address,size,value,unused):
        raise AssertionError((case,hex(address),hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR))))
    cpu.hook_add(UC_HOOK_MEM_INVALID,invalid)
    if integrated:
        def call(address,args=()):
            for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*args,0,0,0,0][:4]):cpu.reg_write(reg,value)
            cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
            cpu.emu_start(address,stop,count=300000)
            assert cpu.reg_read(UC_ARM_REG_PC)==stop
            return cpu.reg_read(UC_ARM_REG_R0)
        call(0x736d0)
        environment=call(0xe5f4);cpu.mem_write(environment+0x20,struct.pack('<I',1))
        call(0x74668,[0,2,0,0]);call(0x17ca34,[0x683400,2,2])
        call(0x17c608,[0x683400,0x4a0111,11,0])
        call(0x17c608,[0x683400,0x4a0116,0,0])
        call(0x17c608,[0x683400,0x4a0111,2,0])
        native_live=True;posts.clear()
    cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
    try:
        cpu.emu_start(base+syms['xw_player_host_remote_page_tick'],stop,count=30000)
    except Exception as error:
        raise AssertionError((case,hex(cpu.reg_read(UC_ARM_REG_PC)),hex(cpu.reg_read(UC_ARM_REG_LR)))) from error
    assert cpu.reg_read(UC_ARM_REG_PC)==stop
    if pair_dialog:
        assert posts==[[0x2010e,0,43,0]],(case,posts)
        assert struct.unpack('<I',cpu.mem_read(sid,4))[0]==13904
        if case=='pair-dialog-expired':
            progress=25
            cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
            cpu.emu_start(base+syms['xw_player_host_remote_page_tick'],stop,count=30000)
            assert posts[-1]==[0x20114,0,43,0] and cancels and not selections
            assert struct.unpack('<I',cpu.mem_read(sid,4))[0]==14400
        elif case!='pair-dialog-show':
            cpu.reg_write(UC_ARM_REG_R0,12);cpu.reg_write(UC_ARM_REG_R1,1 if case=='pair-dialog-yes' else 2)
            cpu.reg_write(UC_ARM_REG_SP,area+0xf000);cpu.reg_write(UC_ARM_REG_LR,stop)
            cpu.emu_start(base+syms['xw_player_host_remote_page_request'],stop,count=30000)
            assert cpu.reg_read(UC_ARM_REG_R0)==(0x57570000 if case=='pair-dialog-yes' else 0x57520000)
            assert bool(selections)==(case=='pair-dialog-yes')
            assert bool(cancels)==(case=='pair-dialog-no')
            assert struct.unpack('<I',cpu.mem_read(sid,4))[0]==14400
        cases[case]=dict(prompt_shown=True,selection_started=bool(selections),original_sid_restored=case!='pair-dialog-show')
        continue
    assert bool(events)==(case in ('found','saved','native-found','native-saved','native-pair-yes','native-pair-no')),(case,events,posts)
    assert bool(commits)==(case=='verified'),case
    assert bool(cancels)==(case in ('failed','timeout','starting-timeout-real','exited-real')),case
    waiting=bool(any(cpu.mem_read(base+syms['pairing_waiting'],4)))
    assert waiting==(case not in ('found','saved','failed','timeout','starting-timeout-real','exited-real','native-found','native-saved','native-pair-yes','native-pair-no')),case
    if integrated:
        assert list(cpu.mem_read(0x683400,2))==[155,1],(case,list(cpu.mem_read(0x683400,2)),posts,audit)
        assert call(native_review['symbols']['wr_remote_page_mac'],[area+0x400])==0
        assert bytes(cpu.mem_read(area+0x400,18))==b'02:11:22:33:44:55\0'
        if case.startswith('native-pair-'):
            call(0x17c608,[0x683400,0x4a0116,0,0])
            assert list(cpu.mem_read(0x683400,2))==[155,2]
            call(base+syms['xw_player_host_remote_page_tick'])
            assert struct.unpack('<I',cpu.mem_read(sid,4))[0]==13904
            choice=1 if case.endswith('yes') else 2
            call(0x17c608,[0x683400,0x4a012e,choice,0])
            assert bool(selections)==(choice==1)
            assert struct.unpack('<I',cpu.mem_read(sid,4))[0]==14400
            assert list(cpu.mem_read(0x683400,2))==([194,1] if choice==1 else [155,2])
    cases[case]=dict(native_confirm_dispatched=bool(events),verified_commit_requested=bool(commits),
                     canceled=bool(cancels),waiting=waiting,posts=posts,original_fsm_executed=integrated)
print(json.dumps(dict(passed=True,library_sha256=digest(library),cases=cases,
                     device_accessed=False,native_dispatch_and_rendering_modeled=True),indent=2))
