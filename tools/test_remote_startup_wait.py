"""Replay the compiled GUI owner tick with modeled Sony queue and startup ports."""
import argparse
import io
import json
import re
import struct
import subprocess

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

from review_managed_remote_profile import digest, receipt


def verify_forget(elf, symbols, pthread_plt):
    base, area, stop = 0x50000000, 0x70000000, 0x7000ff00
    sid = 0x4eb99c + 43 * 48 + 4
    address = bytes.fromhex('020001020304')
    cases = {}
    for case in ('yes', 'no', 'stale-peer', 'wrong-page', 'no-dialog', 'invalid-result', 'abandoned-dialog'):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(base, 0x100000)
        cpu.mem_map(area, 0x10000)
        cpu.mem_map(sid & ~4095, 4096)
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                cpu.mem_write(base + segment['p_vaddr'], segment.data())
        cpu.mem_write(base + symbols['page'], struct.pack('<IIQI', area + 0x100, 17, 41, 1))
        active = case != 'no-dialog'
        cpu.mem_write(base + symbols['pairing_forget_open'], struct.pack('<I', active))
        cpu.mem_write(base + symbols['pairing_peer'], address)
        cpu.mem_write(sid, struct.pack('<I', 13903 if active else 14400))
        attempted = []

        def hook(uc, pc, size, _):
            if pc == base + pthread_plt:
                result = 17
            elif pc == base + symbols['xw_player_remote_page_image_valid']:
                result = 1
            elif pc == base + symbols['wr_view_menu_context']:
                result = 0x683400
            elif pc == base + symbols['wr_view_menu_state']:
                result = 0xc202 if case in ('wrong-page', 'abandoned-dialog') else 0xc203
            elif pc == base + symbols['hb_monotonic_millis']:
                uc.mem_write(uc.reg_read(UC_ARM_REG_R0), struct.pack('<Q', 500))
                result = 0
            elif pc == base + symbols['xw_player_host_remote_pairing_forget']:
                assert bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 6)) == address
                assert uc.reg_read(UC_ARM_REG_R1) == 1
                attempted.append(True)
                result = -5 if case == 'stale-peer' else 1
            else:
                return
            uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        cpu.hook_add(UC_HOOK_CODE, hook)
        cpu.reg_write(UC_ARM_REG_R0, 11)
        cpu.reg_write(UC_ARM_REG_R1, 2 if case == 'no' else 0 if case == 'invalid-result' else 1)
        cpu.reg_write(UC_ARM_REG_SP, area + 0xf000)
        cpu.reg_write(UC_ARM_REG_LR, stop)
        entry = 'xw_player_host_remote_page_tick' if case == 'abandoned-dialog' else 'xw_player_host_remote_page_request'
        cpu.emu_start(base + symbols[entry], stop, count=10000)
        assert cpu.reg_read(UC_ARM_REG_PC) == stop
        assert bool(attempted) == (case in ('yes', 'stale-peer'))
        expected = {'yes': 1, 'no': 0, 'stale-peer': -5}.get(case, -1)
        if case != 'abandoned-dialog':
            assert cpu.reg_read(UC_ARM_REG_R0) == 0x57520000 | (expected & 0xffff)
        restored = case != 'invalid-result'
        assert struct.unpack('<I', cpu.mem_read(sid, 4))[0] == (14400 if restored else 13903)
        assert bool(any(cpu.mem_read(base + symbols['pairing_forget_open'],4))) == (not restored)
        cases[case] = dict(backend_called=bool(attempted), original_sid=restored)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-review', required=True)
    args = parser.parse_args()
    path, review = receipt(args.host_review)
    assert review['shared_wifi_review']
    library = path.parent / 'libx1000-player-analysis.so'
    assert digest(library) == review['library_sha256']
    elf = ELFFile(io.BytesIO(library.read_bytes()))
    symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()
               if s['st_info']['type'] != 'STT_FILE'}
    bss = elf.get_section_by_name('.bss')
    symbols['page'], = (s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()
                        if s.name == 'page' and bss['sh_addr'] <= s['st_value'] < bss['sh_addr'] + bss['sh_size'])
    disassembly = subprocess.check_output(
        ['arm-linux-gnueabi-objdump', '-d', '--disassemble=xw_player_host_remote_page_tick', str(library)],
        text=True)
    pthread_plt = int(re.search(r'\b([0-9a-f]+) <pthread_self@plt>', disassembly)[1], 16)
    base, area, stop = 0x50000000, 0x70000000, 0x7000ff00
    cases = {}
    for case in ('queued', 'starting', 'ready', 'ready-at-deadline', 'failed', 'draining',
                 'timeout', 'fault', 'queue-busy', 'parent-queue-retry'):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(base, 0x100000)
        cpu.mem_map(area, 0x10000)
        for address in (0xa5000, 0x74000, 0x17c000):
            cpu.mem_map(address, 4096)
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                cpu.mem_write(base + segment['p_vaddr'], segment.data())
        cpu.mem_write(base + symbols['page'], struct.pack('<II', area + 0x100, 17))
        for name in ('waiting', 'wait_dialog'):
            cpu.mem_write(base + symbols[name], struct.pack('<I', 1))
        cpu.mem_write(base + symbols['wait_serial'], struct.pack('<Q', 41))
        events = []
        stop_requests = []
        phase = {'queued': 1, 'failed': 1, 'draining': 3, 'fault': 5}.get(case, 2)
        ports = {base + symbols[name]: result for name, result in {
            'xw_player_remote_page_image_valid': 1, 'xw_player_remote_view_image_valid': 1,
            'wr_view_menu_context': 0x683400, 'wr_view_menu_state': 0xc202,
            'wr_native_page_bridge_request': 0x57520000,
        }.items()}
        ports[base + pthread_plt] = 17

        def hook(uc, address, size, _):
            registers = [uc.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            if address in ports:
                result = ports[address]
            elif address == base + symbols['wr_settings_backend_query']:
                uc.mem_write(registers[1], struct.pack('<IIii', phase, case == 'queued', 0, 0))
                result = 0
            elif address == base + symbols['wr_settings_backend_start_result']:
                stage = {'queued': 0, 'starting': 7, 'timeout': 7, 'failed': 5,
                         'draining': 8, 'fault': 8}.get(case, 9)
                serial = 41 if case == 'queued' else 42
                error = -2 if case in ('failed', 'draining', 'fault') else 0
                uc.mem_write(registers[1], struct.pack('<QQiiii', serial, 43, stage, error, 0, 0))
                result = 0
            elif address == base + symbols['hb_monotonic_millis']:
                uc.mem_write(registers[0], struct.pack('<Q', 15000 if case in ('timeout', 'ready-at-deadline') else 500))
                result = 0
            elif address == base + symbols['wr_settings_backend_request_stop']:
                stop_requests.append(True)
                result = 1
            elif address in (0xa57f0, 0x74668, 0x17ca34):
                events.append([address, *(registers[:3] if address == 0x17ca34 else registers)])
                first_parent_post = case == 'parent-queue-retry' and address == 0xa57f0 and len(events) == 2
                result = 0 if case == 'queue-busy' or first_parent_post else 1
            else:
                return
            uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        cpu.hook_add(UC_HOOK_CODE, hook)
        def tick():
            cpu.reg_write(UC_ARM_REG_SP, area + 0xf000)
            cpu.reg_write(UC_ARM_REG_LR, stop)
            cpu.emu_start(base + symbols['xw_player_host_remote_page_tick'], stop, count=10000)
            assert cpu.reg_read(UC_ARM_REG_PC) == stop
        tick()
        if case in ('draining', 'timeout'):
            assert not events and any(cpu.mem_read(base + symbols['waiting'], 4))
            phase = 4  # The child has exited, but the factory has yet to renew.
            tick()
            assert not events and any(cpu.mem_read(base + symbols['waiting'], 4))
            phase = 1
            tick()
        if case == 'parent-queue-retry':
            assert any(cpu.mem_read(base + symbols['waiting'], 4))
            assert len(events) == 2
            tick()
            assert events.pop(2) == events[1]
        completed = case in ('ready', 'ready-at-deadline', 'failed', 'draining',
                             'timeout', 'fault', 'parent-queue-retry')
        assert len(stop_requests) == (case == 'timeout')
        assert bool(any(cpu.mem_read(base + symbols['waiting'], 4))) != completed, (case, events)
        assert events == (
            [[0xa57f0, 0x20114, 0, 113, 0], [0xa57f0, 0x20106, 0, 97, 11],
             [0x74668, 0, 2, 0, 11], [0x17ca34, 0x683400, 2, 1]]
            if completed else [[0xa57f0, 0x20114, 0, 113, 0]] if case == 'queue-busy' else [])
        cases[case] = {'returned_to_settings': completed, 'stop_requested': bool(stop_requests)}
    forget_cases = verify_forget(elf, symbols, pthread_plt) if 'pairing_forget_open' in symbols else {}
    print(json.dumps({'passed': True, 'library_sha256': digest(library), 'cases': cases, 'forget_cases': forget_cases,
                      'device_accessed': False, 'sony_rendering_modeled': True}, indent=2))


if __name__ == '__main__':
    main()
