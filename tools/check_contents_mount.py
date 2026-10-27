"""Replay stock d1c8/12d7c mount path with virtual libc; never mount/format anything."""
from pathlib import Path
import argparse, hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--service-entry',action='store_true',help='Consume original Responder op11 bytes at original fcc8 service.')
options=parser.parse_args()
capture_input=None
if options.service_entry:
    capture_path='sources/native-responder-usb-restore-request.json'
    capture_raw=(ROOT/capture_path).read_bytes();capture=json.loads(capture_raw)
    assert capture['all_passed'] and capture['responder_sha256']=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
    captured=next(row for row in capture['cases'] if row['case']=='active-success')['captured_requests']
    assert len(captured)==1 and captured[0]['words']==[20,55,2,11,66]
    capture_input={'path':capture_path,'sha256':hashlib.sha256(capture_raw).hexdigest(),'request':captured[0]['words']}
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
    binary = tar.extractfile('./usr/local/bin/sysmgrd').read()
assert hashlib.sha256(binary).hexdigest() == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
rows = []
for name, error, readonly, expected in [('writable', 0, 0, 2), ('already-busy', 16, 0, 2),
                                      ('read-only', 0, 1, 3), ('mount-EIO', 5, 0, 4)]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in ELFFile(io.BytesIO(binary)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x100000, 0x10000)
    core, errptr, end = 0x100000, 0x100100, 0x100200
    write = lambda address, value: u.mem_write(address, struct.pack('<I', value))
    write(core + 0x503c, 2)
    write(errptr, error)
    events, requests, replies = [], [], []
    ipc,envelope=0x106000,0x106100
    if options.service_entry:
        u.mem_write(ipc,struct.pack('<II',core,44))
        u.mem_write(envelope,struct.pack('<5I',*capture_input['request']))
    def string(pointer):
        return bytes(u.mem_read(pointer, 128)).split(b'\0', 1)[0].decode()
    def hook(uc, pc, size, unused):
        if pc == end:
            uc.emu_stop()
            return
        if pc not in (0xa188, 0x1c4d0, 0x1c5ac, 0x9b4c, 0x9984, 0x99e4, 0x9a14) + ((0x16d18,) if options.service_entry else ()):
            return
        args = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc == 0x9b4c:
            events.append('sync')
        elif pc == 0x9984:
            data_ptr = struct.unpack('<I', uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 4))[0]
            request = {'source': string(args[0]), 'target': string(args[1]),
                       'filesystem': string(args[2]), 'flags': hex(args[3]), 'options': string(data_ptr)}
            assert request == {'source': '/dev/mtdblock/2', 'target': '/contents', 'filesystem': 'vfat',
                               'flags': '0xc0ed0400', 'options': 'shortname=winnt,iocharset=utf8,dmask=0000,fmask=0000'}
            requests.append(request)
            events.append('mount')
            result = -1 if error else 0
        elif pc == 0x99e4:
            result = errptr
        elif pc == 0x9a14:
            assert string(args[0]) == '/contents'
            uc.mem_write(args[1], b'\0' * 64)
            write(args[1] + 40, readonly)
            events.append('statvfs')
        elif pc == 0x16d18:
            assert args[:2]==[44,66]
            replies.append(list(struct.unpack('<4I',uc.mem_read(args[2],16))))
        uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    u.reg_write(UC_ARM_REG_R0, ipc if options.service_entry else core)
    if options.service_entry:u.reg_write(UC_ARM_REG_R1,envelope)
    u.reg_write(UC_ARM_REG_SP, 0x10f000)
    u.reg_write(UC_ARM_REG_LR, end)
    u.emu_start(0xfcc8 if options.service_entry else 0xd1c8, end, count=3000)
    assert u.reg_read(UC_ARM_REG_PC) == end and u.reg_read(UC_ARM_REG_R0) == 0
    mount_state = struct.unpack('<I', u.mem_read(core + 0x41c8 + 40, 4))[0]
    core_state = struct.unpack('<I', u.mem_read(core + 0x503c, 4))[0]
    assert mount_state == expected and core_state == 1 and len(requests) == 1
    assert events == ['sync', 'sync', 'mount'] + ([] if error == 5 else ['statvfs'])
    if options.service_entry:assert replies==[[16,55,11,0]]
    rows.append({'case': name, 'supplied_errno': error, 'supplied_readonly': bool(readonly),
                 'events': events, 'mount_request': requests[0], 'mount_state': mount_state,
                 'core_state': core_state, 'outer_return': 0,'service_replies':replies})
report = {'sysmgrd_sha256': hashlib.sha256(binary).hexdigest(), 'entry': '0xfcc8' if options.service_entry else '0xd1c8',
          'native_mount_helper': '0x12d7c', 'cases': rows, 'all_passed': True,
          'physical_device_access': False,
          'limits': ['Initial core state2 and libc results are fixtures; original state table and mount logic execute.',
                     'Mount/statvfs/sync/logging are virtual; no host/device mount or format is performed.',
                     'Outer return0 is not proof of writable contents: mount-state field differs on failure/read-only.',
                     'USB disconnection/transfer stop and caller-to-service ordering are not executed.']}
if capture_input:
    report['client_capture']=capture_input
    report['limits'].append('op11 request bytes come from separate original Responder replay; IPC transport and caller timing remain fixtures.')
(ROOT / ('sources/native-contents-mount-service-op11.json' if options.service_entry else 'sources/native-contents-mount.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
