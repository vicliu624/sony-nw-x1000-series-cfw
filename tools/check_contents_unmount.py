"""Replay original contents-unmount wrapper with virtual libc results, offline only."""
from pathlib import Path
import argparse, hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--caller', action='store_true', help='Include original d02c caller; later device-control helper remains virtual.')
parser.add_argument('--native-control', action='store_true', help='Execute128f8, virtualizing only its imports and176c4 notification helper.')
parser.add_argument('--native-usb-allow', action='store_true', help='Also execute176c4; supplied USB connection descriptor and virtual ioctl.')
parser.add_argument('--service-entry', action='store_true', help='Enter original fc60 using op10 captured after original Responder activation/state dispatch.')
options = parser.parse_args()
if options.service_entry:
    options.native_usb_allow = True
if options.native_usb_allow:
    options.native_control = True
if options.native_control:
    options.caller = True
client_capture = None
if options.service_entry:
    capture_path = 'sources/native-responder-activation-usb-request.json'
    capture_raw = (ROOT / capture_path).read_bytes()
    capture = json.loads(capture_raw)
    assert capture['responder_sha256'] == '71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
    assert capture['all_passed']
    captured_case = next(row for row in capture['cases'] if row['case'] == 'active-success')
    assert len(captured_case['captured_requests']) == 1
    assert captured_case['activation_requests'] == [[24, 55, 2, 1, 66, 2]]
    assert captured_case['selected_actions'] == ['0xfa3c'] and captured_case['state_bytes'] == [2, 3]
    client_capture = {'path': capture_path, 'report_sha256': hashlib.sha256(capture_raw).hexdigest(),
                      'request': captured_case['captured_requests'][0]['words']}
    assert client_capture['request'] == [20, 56, 2, 10, 66]
archive = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
    binary = tar.extractfile('./usr/local/bin/sysmgrd').read()
digest = hashlib.sha256(binary).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows = []
for name, error, expected in [('success', 0, 1), ('EINVAL-treated-as-success', 22, 1),
                               ('busy-EBUSY', 16, 5), ('io-error-EIO', 5, 5)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    if options.service_entry:
        assert struct.unpack('<I', u.mem_read(0xeec0, 4))[0] == 0xfc60
        assert struct.unpack('<I', u.mem_read(0xed1c, 4))[0] == 0xe5832028
    u.mem_map(0x100000, 0x10000)
    core, errptr, end = 0x100000, 0x100100, 0x100200
    obj = core + 0x41c8 if options.caller else core
    if options.caller:
        u.mem_write(core + 0x503c, struct.pack('<I', 1))
    if options.native_usb_allow:
        u.mem_write(obj, struct.pack('<I', 91))  # descriptor from original startup, not replayed here
    u.mem_write(errptr, struct.pack('<I', error))
    u.mem_write(obj + 40, struct.pack('<I', 0xaaaaaaaa))
    events = []
    control_requests = []
    replies = []
    ipc, request = 0x106000, 0x106100
    if options.service_entry:
        u.mem_write(ipc, struct.pack('<II', core, 44))
        u.mem_write(request, struct.pack('<5I', *client_capture['request']))
    def hook(uc, address, size, unused):
        if address == end:
            uc.emu_stop()
            return
        if options.caller and address == 0x1c888:
            events.append('fatal-boundary:1c888')
            uc.emu_stop()
            return
        if options.native_control and address == 0x128f8:
            events.append('native-device-control-helper:128f8')
            return
        if options.native_usb_allow and address == 0x176c4:
            events.append('native-usb-allow-helper:176c4')
            return
        extras = (0x13680, 0x128f8, 0x1e518, 0x1b594) if options.caller else ()
        if options.native_control:
            extras += (0x9ca8, 0x9a5c, 0x9960, 0x176c4)
        if options.native_usb_allow:
            extras += (0x17588, 0x1c5ac)
        if options.service_entry:
            extras += (0x16d18,)
        if address not in (0x9b4c, 0x9a2c, 0x99e4, 0xa188, 0x1c4d0) + extras:
            return
        value = 0
        if address == 0x9b4c:
            events.append('sync')
        elif address == 0x9a2c:
            pointer = uc.reg_read(UC_ARM_REG_R0)
            path = bytes(uc.mem_read(pointer, 32)).split(b'\0', 1)[0].decode()
            assert path == '/contents'
            events.append('umount:/contents')
            value = -1 if error else 0
        elif address == 0x99e4:
            value = errptr
        elif address == 0x1c4d0:
            events.append('log')
        elif address == 0x13680:
            events.append('virtual-pre-unmount-helper:13680')
        elif address == 0x128f8:
            events.append('virtual-device-control-helper:128f8')
        elif address == 0x9ca8:
            path = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 32)).split(b'\0', 1)[0].decode()
            assert path == '/dev/mgscsi' and uc.reg_read(UC_ARM_REG_R1) == 1
            events.append('open:/dev/mgscsi')
            value = 77
        elif address == 0x9a5c:
            args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            assert args in ([77, 0x40017325, 1], [91, 0x40046702, 0])
            control_requests.append({'fd': args[0], 'request': hex(args[1]), 'argument': args[2]})
            events.append('ioctl:40017325:1' if args[0] == 77 else 'ioctl:40046702:0')
        elif address == 0x9960:
            assert uc.reg_read(UC_ARM_REG_R0) == 77
            events.append('close:mgscsi')
        elif address == 0x176c4:
            events.append('virtual-post-control-helper:176c4')
        elif address == 0x16d18:
            assert uc.reg_read(UC_ARM_REG_R0) == 44 and uc.reg_read(UC_ARM_REG_R1) == 66
            replies.append(list(struct.unpack('<4I', uc.mem_read(uc.reg_read(UC_ARM_REG_R2), 16))))
            events.append('virtual-service-reply')
        uc.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, ipc if options.service_entry else core if options.caller else obj)
    if options.service_entry:
        u.reg_write(UC_ARM_REG_R1, request)
    u.reg_write(UC_ARM_REG_SP, 0x10f000)
    u.reg_write(UC_ARM_REG_LR, end)
    u.emu_start(0xfc60 if options.service_entry else 0xd02c if options.caller else 0x12e84, end, count=3000)
    state = struct.unpack('<I', u.mem_read(obj + 40, 4))[0]
    result = u.reg_read(UC_ARM_REG_R0)
    assert state == expected
    if options.caller:
        assert events[:4] == ['virtual-pre-unmount-helper:13680', 'sync', 'sync', 'umount:/contents']
        control_event = 'native-device-control-helper:128f8' if options.native_control else 'virtual-device-control-helper:128f8'
        assert (control_event in events) == (expected == 1)
        assert ('fatal-boundary:1c888' in events) == (expected == 5)
        if options.native_control:
            assert len(control_requests) == ((2 if options.native_usb_allow else 1) if expected == 1 else 0)
            if expected == 1:
                assert events.index('umount:/contents') < events.index('open:/dev/mgscsi') < events.index('ioctl:40017325:1') < events.index('close:mgscsi')
                if options.native_usb_allow:
                    assert control_requests[1] == {'fd': 91, 'request': '0x40046702', 'argument': 0}
                    assert events.index('close:mgscsi') < events.index('ioctl:40046702:0')
        if expected == 1:
            assert u.reg_read(UC_ARM_REG_PC) == end and result == 0
            assert struct.unpack('<I', u.mem_read(core + 0x503c, 4))[0] == 2
    else:
        assert u.reg_read(UC_ARM_REG_PC) == end
        assert result == (0 if expected == 1 else 0x1d08)
        assert events == ['sync', 'sync', 'umount:/contents'] + (['log'] if error else [])
    if options.service_entry:
        assert replies == ([[16, client_capture['request'][1], 10, 0]] if expected == 1 else [])
    rows.append({'case': name, 'supplied_errno': error, 'events': events,
                 'returned_to_caller': u.reg_read(UC_ARM_REG_PC) == end,
                 'return': hex(result) if u.reg_read(UC_ARM_REG_PC) == end else None,
                 'object_plus_40': state, 'control_requests': control_requests, 'service_replies': replies})
report = {'sysmgrd_sha256': digest, 'entry': '0xfc60' if options.service_entry else '0xd02c' if options.caller else '0x12e84', 'native_unmount_helper': '0x12b40',
          'cases': rows, 'all_passed': True, 'physical_device_access': False,
          'limits': ['libc sync/umount/errno and logging are virtual.',
                     'Original success/failure classification executes; no filesystem is mounted or unmounted.',
                     '13680/logging are virtual; fatal handler is intercepted.128f8/176c4 execute only in their requested modes; libc imports remain virtual.',
                     'Actual device control, USB transport and link from application reaper are not validated.']}
report['native_control_executed'] = options.native_control
report['native_usb_allow_executed'] = options.native_usb_allow
report['native_service_entry_executed'] = options.service_entry
if options.service_entry:
    report['client_capture'] = client_capture
    report['limits'].append('op10 bytes are captured from a separate original Responder replay; IPC context, dispatch transport and requesting UI lifecycle remain fixtures.')
if options.native_usb_allow:
    report['limits'].append('176c4 executes, but descriptor91 and startup context are supplied; kernel USB callback is not executed.')
filename = 'native-contents-service-op10.json' if options.service_entry else 'native-contents-usb-allow.json' if options.native_usb_allow else 'native-contents-unmount-control.json' if options.native_control else 'native-contents-unmount-caller.json' if options.caller else 'native-contents-unmount.json'
(ROOT / 'sources' / filename).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
