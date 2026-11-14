"""Run the exact shared Wi-Fi DSO's deferred confirmation in ARM emulation."""
import argparse
import hashlib
import io
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
)

from review_managed_remote_profile import digest, receipt
from wireless_callback_bridge import offset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-review',required=True)
    args=parser.parse_args()
    path, review=receipt(args.host_review)
    assert review.get('shared_wifi_review')
    library=path.parent/'libx1000-player-analysis.so'
    player=path.parent/'SpiderApp.player-prepare.analysis-only.elf'
    assert digest(library)==review['library_sha256'] and digest(player)==review['candidate_sha256']
    raw=player.read_bytes()
    dispatcher=offset(raw,0x17c608,0x384)
    expected=hashlib.sha256(raw[dispatcher:dispatcher+0x384]).digest()
    elf=ELFFile(io.BytesIO(library.read_bytes()))
    symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    base,stop=0x50000000,0x7000ff00
    rows=[]
    for case in ('ready','busy','native-ready','native-busy','native-fault','denied','left-page','changed-row','exiting','bad-image','bad-dispatch'):
        cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        cpu.mem_map(base,0x100000);cpu.mem_map(0x70000000,0x10000)
        cpu.mem_map(0x17c000,4096);cpu.mem_map(0x4ee000,4096)
        for segment in elf.iter_segments():
            if segment['p_type']=='PT_LOAD':cpu.mem_write(base+segment['p_vaddr'],segment.data())
        pending=base+symbols['wifi_off_pending']
        cpu.mem_write(pending,struct.pack('<I',1))
        if case.startswith('native-'):
            cpu.mem_write(base+symbols['wireless_setting']+12,struct.pack('<I',1))
        cpu.mem_write(0x4ee5d8,struct.pack('<I',int(case!='changed-row')))
        assert bytes(cpu.mem_read(base+symbols['wifi_off_dispatch_digest'],32))==expected
        ports={base+symbols[name]:value for name,value in {
            'xw_player_host_original_exiting':int(case=='exiting'),
            'xw_player_remote_page_image_valid':int(case!='bad-image'),
            'xw_player_remote_view_image_valid':1,
            'wr_view_menu_context':0x683400,
            'wr_view_menu_state':0x5a02 if case=='left-page' else 0x9a02,
            'xw_player_host_remote_before_wifi_off':1 if case=='busy' else -3 if case=='denied' else 0,
            'xw_wireless_setting_poll':1 if case=='native-busy' else -3 if case=='native-fault' else 0,
            'xw_stock_image_match':-1 if case=='bad-dispatch' else 0,
        }.items()}
        dispatched=[]
        def hook(uc,address,size,unused):
            if address==0x17c608:
                dispatched.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
                assert not any(uc.mem_read(pending,4))
                value=0
            elif address in ports:
                value=ports[address]
                if address==base+symbols['xw_stock_image_match']:
                    assert uc.reg_read(UC_ARM_REG_R0)==0x17c608 and uc.reg_read(UC_ARM_REG_R1)==0x384
                    assert bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R2),32))==expected
            else:
                return
            uc.reg_write(UC_ARM_REG_R0,value&0xffffffff)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        cpu.hook_add(UC_HOOK_CODE,hook)
        for _ in range(2):
            cpu.reg_write(UC_ARM_REG_SP,0x7000f000);cpu.reg_write(UC_ARM_REG_LR,stop)
            cpu.emu_start(base+symbols['wifi_off_resume'],stop,count=10000)
            assert cpu.reg_read(UC_ARM_REG_PC)==stop
        assert dispatched==([[0x683400,0x4a0119,0xff0000,0]] if case in ('ready','native-ready') else [])
        retained=bool(any(cpu.mem_read(pending,4)))
        assert retained==(case in ('busy','native-busy'))
        rows.append(dict(case=case,dispatched=dispatched,pending_retained=retained))
    print(json.dumps(dict(passed=True,library_sha256=review['library_sha256'],cases=rows,
                          source_sha256=digest(__import__('pathlib').Path(__file__)),
                          modeled_ports_and_dispatch=True,device_accessed=False),indent=2))


if __name__=='__main__':
    main()
