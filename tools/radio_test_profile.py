"""Reviewed radio profiles and isolated MCU fixtures for instruction replay."""
import hashlib
import sys
import struct
from pathlib import Path
from app_registry import ROOT
from generate_espnow_full_profile import reviewed_radio

def selected_radio():
    if '--radio-review' not in sys.argv:
        return None
    index = sys.argv.index('--radio-review')
    if index + 1 >= len(sys.argv):
        raise ValueError('--radio-review requires a local build directory')
    return reviewed_radio(sys.argv[index + 1])


def packet_fixture(blocks=3):
    """Start a fresh stock packet pool with modeled ROM calls and queue."""
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                 UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
    from marvell_firmware import parse

    blob = (ROOT / 'work/targets-jp/sd8686.bin').read_bytes()
    assert hashlib.sha256(blob).hexdigest() == '08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
    records = parse(blob)
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for base, size in ((0, 0x20000), (0xC0000000, 0x20000), (0x04000000, 0x4000),
                       (0x200000, 0x10000), (0xFFFF0000, 0x10000)):
        cpu.mem_map(base, size)
    for record in records:
        if record.command == 1:
            cpu.mem_write(record.address, record.data)
    if blocks == 3:
        cpu.mem_write(0x163EE, bytes.fromhex('0322'))
    reserved = 0xC000A190
    sentinel = bytes([0xA5]) * 1900
    cpu.mem_write(reserved, sentinel)
    queued, notified, queue_result = [], [], [0]

    def word(address):
        return struct.unpack('<I', cpu.mem_read(address, 4))[0]

    def put(address, value):
        cpu.mem_write(address, struct.pack('<I', value))

    def ret(value=0):
        cpu.reg_write(UC_ARM_REG_R0, value)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def hook(machine, pc, size, unused):
        if pc == 0x1F000:
            machine.emu_stop()
        elif pc in (0xFA94, 0xFAA0, 0x65C4, 0x5710):
            # Model unrelated setup and a plaintext peer without a key entry.
            ret()
        elif pc == 0x758:
            address = machine.reg_read(UC_ARM_REG_R0)
            length = machine.reg_read(UC_ARM_REG_R1)
            assert address == 0xC0014770 and length == 24
            machine.mem_write(address, bytes(length))
            ret(address)
        elif pc == 0x7B4:
            dest, source, length = (machine.reg_read(reg) for reg in
                                    (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            assert 0 <= length <= 1700
            machine.mem_write(dest, bytes(machine.mem_read(source, length)))
            ret(dest)
        elif pc == 0xFFFF1D2C:
            handle, slot, timeout = (machine.reg_read(reg) for reg in
                                     (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            assert handle == 0x12340003 and timeout == 0
            queued.append(word(slot))
            ret(queue_result[0])
        elif pc == 0xFFFF1518:
            target, event, option = (machine.reg_read(reg) for reg in
                                     (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            assert target == 0x04001970 and event == 2 and option == 0
            notified.append((target, event))
            ret()

    cpu.hook_add(UC_HOOK_CODE, hook)

    def call(entry, *args):
        cpu.reg_write(UC_ARM_REG_SP, 0x208000)
        cpu.reg_write(UC_ARM_REG_LR, 0x1F001)
        registers = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
        for reg, value in zip(registers, args):
            cpu.reg_write(reg, value)
        cpu.emu_start(entry if entry == 0x1360 else entry | 1, 0x1F002, count=20000)
        assert cpu.reg_read(UC_ARM_REG_PC) == 0x1F000, hex(cpu.reg_read(UC_ARM_REG_PC))
        return cpu.reg_read(UC_ARM_REG_R0)
    call(0xc0004b6c)
    manager=0xc000d5a4;descriptor=word(0xc000ee50)
    assert descriptor==0xc0014728 and word(descriptor+20)==manager
    assert bytes(cpu.mem_read(descriptor,4))==bytes.fromhex('20004400')
    assert word(descriptor+12)==0x102dd and word(descriptor+16)==0x1031d
    def free_count():return struct.unpack('<H',cpu.mem_read(manager+8,2))[0]
    assert free_count()==blocks
    put(0x04001bc8,0x200400);put(0x04001bc4,0x200420)
    cpu.mem_write(0x200400,bytes(32));cpu.mem_write(0x200420,bytes.fromhex('021122334455'))
    cpu.mem_write(0x200440,bytes.fromhex('0266778899aa'));cpu.mem_write(0x200460,b'\xff'*6)
    put(0x040015e0+3*4,0x12340003)
    return dict(cpu=cpu, word=word, put=put, call=call, free_count=free_count,
                blob=blob, queue_result=queue_result, queued=queued, notified=notified,
                reserved=reserved, sentinel=sentinel, descriptor=descriptor)


WORD_REQUEST = 0xC00155B8
WORD_LINKER = ('ENTRY(xnow_radio_word_command_entry)\nSECTIONS { . = 0xc000a190; '
               '.text : { *(.text*) *(.rodata*) } .state : { *(.state) } '
               '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } '
               'ASSERT(.<=0xc000a8fc,"reserved block exceeded") }')


def word_command(cpu):
    """Issue one host command through the original MCU dispatcher."""
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                 UC_ARM_REG_R6, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

    def responses(machine, pc, size, unused):
        if pc == 0x9A46:
            machine.emu_stop()
        elif pc == 0x9C90:
            dest, source, length = (machine.reg_read(reg) for reg in
                                    (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            machine.mem_write(dest, bytes(machine.mem_read(source, length)))
            machine.reg_write(UC_ARM_REG_R0, dest)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, responses)

    def command(address, value):
        request = struct.pack('<4H', 0x86, 20, 0x55AA, 0) + struct.pack('<HHII', 1, 0, address, value)
        cpu.mem_write(WORD_REQUEST, request)
        cpu.mem_write(0xC000EDF4, b'\0')
        cpu.reg_write(UC_ARM_REG_SP, 0x208000)
        cpu.reg_write(UC_ARM_REG_LR, 0x1F001)
        cpu.emu_start(0x8079, 0x9B40, count=30000)
        assert cpu.reg_read(UC_ARM_REG_PC) == 0x9A46 and cpu.reg_read(UC_ARM_REG_R6) == 0

    return command


def build_wire_codec(output):
    """Build the real host encoder for tests that need encoded frames."""
    import ctypes
    import subprocess

    shared = output / 'wire.so'
    subprocess.run(['gcc', '-std=c99', '-shared', '-fPIC', 'runtime/platform/espnow/xnow_wire.c',
                    '-o', str(shared)], cwd=ROOT, check=True)
    codec = ctypes.CDLL(str(shared))
    codec.xnow_espnow_encode_body.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
    ]
    return codec


def frame_fixture(payload, manifest):
    """Load the exact frame profile and model original host-command delivery."""
    import ctypes

    from elftools.elf.elffile import ELFFile
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import (
        UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4,
        UC_ARM_REG_R5, UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    )

    assert manifest.get("frame_transactions") and manifest["rx_diagnostics"]
    env = packet_fixture()
    cpu, put, word, call, free_count = [
        env[n] for n in ("cpu", "put", "word", "call", "free_count")
    ]
    with payload.open("rb") as stream:
        elf = ELFFile(stream)
        sections = [
            (s["sh_addr"], s.data())
            for s in elf.iter_sections()
            if s["sh_flags"] & 2 and s["sh_size"]
        ]
        symbols = {
            s.name: s["st_value"]
            for s in elf.get_section_by_name(".symtab").iter_symbols()
            if s.name
        }
    assert max(a + len(b) for a, b in sections) <= 0xC000A8FC
    for a, b in sections:
        cpu.mem_write(a, b)
    for patch in manifest["patches"]:
        cpu.mem_write(patch["address"], bytes.fromhex(patch["after"]))
    tx = symbols["xnow_full_tx"]
    completion = symbols["xnow_tx_completion"]
    request, response = 0xC00155B8, 0xC0014E4C
    copies = []
    saved = {}


    def hook(u, pc, n, unused):
        if pc == 0x88D6:
            saved.update(
                (r, u.reg_read(r))
                for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R7, UC_ARM_REG_SP)
            )
        elif pc == 0x9A46:
            assert all(u.reg_read(r) == v for r, v in saved.items())
        elif pc == 0x9A70:
            u.emu_stop()
        elif pc == 0x9C90:
            dst, src, length = [
                u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)
            ]
            assert 0 <= length <= (1500 if dst == response else 1536)
            copies.append((dst, src, length))
            u.mem_write(dst, bytes(u.mem_read(src, length)))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))


    cpu.hook_add(UC_HOOK_CODE, hook)


    def command(action, body, size=None, count=0, address=0xC000D5A8):
        size = 16 + len(body) if size is None else size
        packet = (
            struct.pack("<4H", 0x86, size, 0x55AA, 0)
            + struct.pack("<HHI", action, count, address)
            + body
        )
        cpu.mem_write(request, packet)
        cpu.mem_write(response, b"\xa5" * 1600)
        cpu.mem_write(0xC0007859, b"\x01")
        cpu.mem_write(0xC000EDF4, b"\0")
        cpu.mem_write(0xC001452A, b"\x01")
        cpu.reg_write(UC_ARM_REG_SP, 0x208000)
        cpu.emu_start(0x8079, 0x9B40, count=50000)
        assert cpu.reg_read(UC_ARM_REG_PC) == 0x9A70
        returned = struct.unpack("<H", cpu.mem_read(response + 2, 2))[0]
        assert 16 <= returned <= 1500 and copies[-1] == (response, request, returned)
        assert bytes(cpu.mem_read(response + returned, 4)) == b"\xa5" * 4
        result = bytes(cpu.mem_read(response, returned))
        assert struct.unpack_from("<H", result)[0] == 0x8086
        return struct.unpack_from("<H", result, 6)[0], result


    def fragment(
        total, data, offset=0, kind=4, wanted=None, mac=bytes.fromhex("0266778899aa"), **kw
    ):
        wanted = word(tx + 8) if wanted is None else wanted
        wire = (
            struct.pack("<III", total, wanted, kind)
            + mac
            + b"\0\0"
            + data
            + bytes((-len(data)) % 4)
        )
        status, result = command(2, wire, count=offset, **kw)
        if status:
            return status, None
        assert len(result) == 36 and struct.unpack_from("<I", result, 16)[0] == 0x314D5246
        assert struct.unpack_from("<I", result, 28)[0] == wanted
        return 0, dict(
            ack=struct.unpack_from("<I", result, 20)[0],
            result=ctypes.c_int32(struct.unpack_from("<I", result, 24)[0]).value,
            packet=struct.unpack_from("<I", result, 32)[0],
        )


    def finish():
        p = word(completion)
        assert p and free_count() == 2
        token = word(completion + 4)
        claim = call(symbols["xnow_radio_tx_observe"], p, 0, 0x70302)
        assert call(0x1360, p) == 0 and free_count() == 3
        call(symbols["xnow_radio_tx_released"], claim)
        status, data = command(3, struct.pack("<7I", token, 0, 0, 0, 0, 0, 0))
        assert (
            not status
            and len(data) == 44
            and struct.unpack_from("<4I", data, 16) == (0x314D5246, token, 0, 0)
        )
        assert word(completion + 20) == token and not word(completion)

    return dict(env=env, symbols=symbols, sections=sections, tx=tx, completion=completion,
                command=command, fragment=fragment, finish=finish, copies=copies)


def legacy_completion_fixture(output, selected):
    """Initialize a legacy word-command profile and its original completion path."""
    import subprocess
    from elftools.elf.elffile import ELFFile
    from unicorn import UC_HOOK_CODE
    from unicorn.arm_const import (
        UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R4, UC_ARM_REG_R5,
        UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    )

    env=packet_fixture()
    cpu,put,word,call,free_count=[env[n] for n in ('cpu','put','word','call','free_count')]
    command=word_command(cpu)
    sources=['runtime/platform/espnow/'+n for n in ('radio_packet.c','radio_full_rx.c','radio_full_tx.c','radio_tx_completion.c','radio_completion_hook.S','radio_word_command.c','radio_command_hook.S')]
    if selected:
        elf=selected[0]
    else:
        output.mkdir(parents=True, exist_ok=True)
        elf=output/'completion.elf'
        link=output/'completion.ld'
        link.write_text(WORD_LINKER)
        subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-mthumb','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(link),*sources,'-o',str(elf)],cwd=ROOT,check=True)
    with elf.open('rb') as f:
     e=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']];symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
    cpu.mem_write(0xc000a190,bytes(1900))
    for a,d in sections:cpu.mem_write(a,d)
    cpu.ctl_remove_cache(0xc000a190,0xc000a8fc)
    state=symbols['xnow_full_tx'];completion=symbols['xnow_tx_completion']
    if selected:
     patch=selected[1]['patches'][2]
     cpu.mem_write(patch['address'],bytes.fromhex(patch['after']))
    else:
     cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
    cpu.ctl_remove_cache(0,0x20000)
    # Hook the common wrapper rather than only task3's call site.
    original=bytes(cpu.mem_read(0xd51c,8));assert original==bytes.fromhex('80b5f3f720ef80bd')
    cpu.mem_write(0xd51c,struct.pack('<HHI',0x4b00,0x4718,symbols['xnow_radio_completion_entry']|1))
    cpu.ctl_remove_cache(0xd51c,0xd524)
    seq=100;releases=[]
    def stop(u,pc,size,unused):
     if pc==0x1360:
      packet=u.reg_read(UC_ARM_REG_R0)
      if word(completion) in (packet,packet+1):assert word(completion+8)!=word(completion+4),'published completion before original free'
      releases.append(packet)
     if pc==0x3a16:u.emu_stop()
    cpu.hook_add(UC_HOOK_CODE,stop)
    def operation(kind):
     nonlocal seq
     command(state+16,kind);seq+=1;command(state+4,seq)
     assert word(state+8)==seq
     return struct.unpack('<i',cpu.mem_read(state+12,4))[0]
    def submit():
     assert operation(1)==0
     packet=word(state+24);cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11))
     command(state+20,15);command(state+32,0x88776602);command(state+36,0xaa99)
     assert operation(2)==0 and word(completion)==packet and word(completion+4)==seq
     return packet,seq
    def finish(packet,status,raw):
     regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7);values=(packet,0x5555,0x6666,0x7777)
     for reg,value in zip(regs,values):cpu.reg_write(reg,value)
     cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
     put(0x208008,status);put(0x20800c,raw);put(0xc0008a08,7)
     before=len(releases);cpu.emu_start(0x3a0d,0x3a18,count=30000)
     assert cpu.reg_read(UC_ARM_REG_PC)==0x3a16 and cpu.reg_read(UC_ARM_REG_SP)==0x208000
     assert cpu.reg_read(UC_ARM_REG_R0)==7 and cpu.reg_read(UC_ARM_REG_R1)==0xc0008a08
     assert tuple(cpu.reg_read(reg) for reg in regs)==values
     assert releases[before:]==[packet]
    report={'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'tools/radio_test_profile.py']}}
    if selected:
     report['exact_selected_radio']=dict(elf=elf.relative_to(ROOT).as_posix(),sha256=selected[1]['payload_elf_sha256'],candidate_sha256=selected[1]['candidate_sha256'])
     report['source_hashes'].update(selected[1]['source_hashes'])
    report['source_hashes']['tools/marvell_firmware.py']=hashlib.sha256((ROOT/'tools/marvell_firmware.py').read_bytes()).hexdigest()
    for name in ('radio_packet.h','radio_full_rx.h','radio_tx_completion.h'):
     name='runtime/platform/espnow/'+name
     report['source_hashes'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    return dict(env=env, symbols=symbols, state=state, completion=completion, sections=sections,
                releases=releases, command=command, operation=operation, submit=submit, finish=finish,
                provenance=report)
