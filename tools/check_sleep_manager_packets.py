"""Original manager command18 handler through pending-client sleep gating."""
from pathlib import Path
from check_sleep_storage_paths import SleepManager
import hashlib
import json
import struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]


def manager_packet_fixture(manager):
    ipc, packet = 0x60006000, 0x60006100
    manager.cpu.mem_write(ipc, struct.pack('<2I', manager.core, 44))
    replies = []

    def capture_reply(cpu, pc, size, context):
        if pc != 0x16d18:
            return
        args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        assert args[:2] == [44, 55] and args[3] == 16
        replies.append(list(struct.unpack('<4I', cpu.mem_read(args[2], 16))))
        cpu.reg_write(UC_ARM_REG_R0, 0)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    manager.cpu.hook_add(UC_HOOK_CODE, capture_reply)
    return ipc, packet, replies


def main():
    manager = SleepManager()
    u, core = manager.cpu, manager.core
    ipc, packet, replies = manager_packet_fixture(manager)
    put, word = manager.put, manager.word
    request19_helpers = []
    prepare_notices = []
    prepare_fixture = False
    def hook(cpu, pc, size, unused):
        if prepare_fixture and pc in (0x11858, 0x115ec, 0x6001ffe0):
            args = [cpu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            if pc == 0x11858:
                assert args[0] == core and args[2] == 16
                cpu.mem_write(args[1], struct.pack('<2I', 1, 2))
                put(args[3], 2)
            elif pc == 0x115ec:
                assert args[:2] in ([core, 1], [core, 2])
                put(args[2], 2)
            else:
                assert args[1] == 99
                prepare_notices.append(list(struct.unpack('<3I', cpu.mem_read(args[0], 12))))
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
        if pc in (0x14030, 0x13c44, 0x14720, 0x121f8, 0xae68):
            request19_helpers.append([hex(pc), cpu.reg_read(UC_ARM_REG_R0), cpu.reg_read(UC_ARM_REG_R1)])
            cpu.reg_write(UC_ARM_REG_R0, 0)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))
            return
    u.hook_add(UC_HOOK_CODE, hook)
    # Cross-check known operation1/7 before executing the registration stores.
    assert word(0xee98 + 1 * 4) == 0xf75c
    assert word(0xee98 + 7 * 4) == 0xfb1c
    assert word(0xee98 + 18 * 4) == 0xffb0
    # Execute the original straight-line registration block, rather than treating
    # adjacent literal addresses as an opcode table by inference.
    u.emu_start(0xecc0, 0xed68, count=1000)
    assert u.reg_read(UC_ARM_REG_PC) == 0xed68
    registration = word(0xee94)
    assert word(registration + 18 * 4) == 0xffb0
    assert word(registration + 19 * 4) == 0x1001c
    # Original request17 -> state3 -> original pending-list construction -> callback3.
    assert word(registration + 17 * 4) == 0xff48
    put(core + 0x503c, 1)
    put(core + 0x51b4, 0x6001ffe0)
    put(core + 0x51b8, 99)
    prepare_fixture = True
    u.mem_write(packet, struct.pack('<5I', 20, 6, 1, 17, 55))
    for register, value in ((UC_ARM_REG_R0, ipc), (UC_ARM_REG_R1, packet),
                            (UC_ARM_REG_SP, manager.stack), (UC_ARM_REG_LR, manager.stop)):
        u.reg_write(register, value)
    u.emu_start(0xff48, manager.stop, count=500000)
    assert u.reg_read(UC_ARM_REG_PC) == manager.stop
    assert replies[-1] == [16, 6, 17, 0]
    assert word(core + 0x503c) == 3
    assert [word(core + 0x5168 + index * 4) for index in range(16)] == [1, 2] + [0] * 14
    assert prepare_notices == [[3, 0, 0]]
    prepare_fixture = False
    put(core + 0x503c, 3)
    put(core + 0x5164, 0)
    for index in range(16):
        put(core + 0x5168 + index * 4, 0)
    put(core + 0x5168, 1)
    put(core + 0x516c, 2)
    rows = []
    for sequence, app_id in enumerate((1, 2)):
        u.mem_write(packet, struct.pack('<5I', 20, sequence, app_id, 18, 55))
        manager.events.clear()
        for register, value in ((UC_ARM_REG_R0, ipc), (UC_ARM_REG_R1, packet),
                                (UC_ARM_REG_SP, manager.stack), (UC_ARM_REG_LR, manager.stop)):
            u.reg_write(register, value)
        u.emu_start(0xffb0, manager.stop, count=500000)
        assert u.reg_read(UC_ARM_REG_PC) == manager.stop
        assert replies[-1] == [16, sequence, 18, 0], replies
        pending = [word(core + 0x5168 + index * 4) for index in range(16)]
        asleep = any(event[0] == 'write' and event[2] == 'S3' for event in manager.events)
        assert asleep == (app_id == 2)
        assert pending == ([0, 2] + [0] * 14 if app_id == 1 else [0] * 16)
        rows.append(dict(app_id=app_id, peer_id=55, reply=replies[-1], pending=pending,
                         sleep_requested=asleep, events=list(manager.events)))
    request19 = []
    for core_state, parameter, expected in ((3, 0, 0x1d03), (4, 0, 0x1d03), (2, 3, 0x102)):
        put(core + 0x503c, core_state)
        u.mem_write(packet, struct.pack('<6I', 24, 11, 1, 19, 55, parameter))
        manager.events.clear()
        for register, value in ((UC_ARM_REG_R0, ipc), (UC_ARM_REG_R1, packet),
                                (UC_ARM_REG_SP, manager.stack), (UC_ARM_REG_LR, manager.stop)):
            u.reg_write(register, value)
        u.emu_start(0x1001c, manager.stop, count=500000)
        assert u.reg_read(UC_ARM_REG_PC) == manager.stop
        assert replies[-1] == [16, 11, 19, expected]
        assert not any(event[0] == 'write' for event in manager.events)
        request19.append(dict(core_state=core_state, parameter=parameter, reply=replies[-1]))
    function_name = bytes(u.mem_read(0x214a8, 128)).split(b'\0', 1)[0].decode()
    accepted19 = []
    for parameter in (0, 1, 2):
        put(core + 0x503c, 2)
        u.mem_write(packet, struct.pack('<6I', 24, 12, 1, 19, 55, parameter))
        request19_helpers.clear()
        manager.events.clear()
        for register, value in ((UC_ARM_REG_R0, ipc), (UC_ARM_REG_R1, packet),
                                (UC_ARM_REG_SP, manager.stack), (UC_ARM_REG_LR, manager.stop)):
            u.reg_write(register, value)
        u.emu_start(0x1001c, manager.stop, count=500000)
        assert u.reg_read(UC_ARM_REG_PC) == manager.stop
        assert replies[-1] == [16, 12, 19, 0]
        assert word(core + 0x503c) == 6 and word(core + 0x51a8) == parameter
        assert request19_helpers[-1] == ['0xae68', core, 0]
        assert not any(event[0] == 'write' for event in manager.events)
        accepted19.append(dict(parameter=parameter, reply=replies[-1], manager_state=6,
                               helpers=list(request19_helpers)))
    report = dict(passed=True, sysmgrd_sha256=manager.digest, cases=rows,
        command17_prepare=dict(reply=[16, 6, 17, 0], manager_state=3,
                               pending=[1, 2] + [0] * 14, callback_notices=prepare_notices),
        registration_block_executed=['0xecc0', '0xed68'], command19_rejections=request19,
        command19_accepted=accepted19,
        command19_core_assertion_text=function_name,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        physical_device_access=False,
        limits=['Original handler registration, command17 state transition/list construction/callback3 and command18 pending-client removal/sleep execute; command19 transitions execute.',
                'Application IDs/statuses and final callback transport are fixtures; notification3 delivery into SpiderApp is checked separately.',
                'Command19 timer/adapter/list-notification helpers are intercepted; ae68 delivery is not executed.',
                'Initial manager state/pending IDs, policy, timer, libc and transport are fixtures.',
                'No upstream request dispatcher, real IPC, physical suspend or wake restoration is qualified.'])
    (ROOT / 'work/remote-sleep-manager-packets-latest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
