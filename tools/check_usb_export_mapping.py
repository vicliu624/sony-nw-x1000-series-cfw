"""Inspect stock USB export configuration offline; never open a device."""
from pathlib import Path
import hashlib
import io
import json
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
    script = archive.extractfile('./usr/local/bin/load_usb_epson').read()
    module = archive.extractfile('./lib/modules/g_nwm_msc.ko').read()
text = script.decode('ascii')
assert 'PID_ICX_1135=0x0399' in text
assert 'g_nwm_msc.ko removable file=/dev/mtdblock/2' in text
assert hashlib.sha256(module).hexdigest() == '084bec059243f852c8b14f5feeac965534c9345e19302b96b9ac8bf1d32c197e'
# Fixed JP1.11 module only. Inspect executable .text bytes, not a GPL macro.
assert module[:6] == b'\x7fELF\x01\x01'
section_offset = struct.unpack_from('<I', module, 32)[0]
entry_size, section_count, names_index = struct.unpack_from('<HHH', module, 46)
sections = [struct.unpack_from('<10I', module, section_offset + i * entry_size)
            for i in range(section_count)]
names = sections[names_index]
strings = module[names[4]:names[4] + names[5]]
code_section = next(s for s in sections if strings[s[0]:].split(b'\0', 1)[0] == b'.text')
code = module[code_section[4]:code_section[4] + code_section[5]]
instructions = {
    0x940: (0xe1a03582, 'do_read: high half of 64-bit LBA shifted left 11'),
    0x94c: (0xe1a05581, 'do_read: low half of LBA shifted left 11'),
    0xc94: (0xe1a03585, 'do_write: high half of 64-bit LBA shifted left 11'),
    0xc9c: (0xe1a04584, 'do_write: low half of LBA shifted left 11'),
}
for offset, (word, description) in instructions.items():
    assert struct.unpack_from('<I', code, offset)[0] == word, description
capacity_raw = (ROOT / 'sources/native-usb-read-capacity.json').read_bytes()
capacity = json.loads(capacity_raw)
assert capacity['module_sha256'] == hashlib.sha256(module).hexdigest()
assert capacity['all_passed'] and len(capacity['cases']) == 4
assert all(row['block_bytes'] == 2048 for row in capacity['cases'])
result = {
    'stock_rootfs_sha256': hashlib.sha256(raw).hexdigest(),
    'usb_loader_sha256': hashlib.sha256(script).hexdigest(),
    'msc_module_sha256': hashlib.sha256(module).hexdigest(),
    'normal_usb_backing_device': '/dev/mtdblock/2',
    'icx1135_configured_usb_pid': '0399',
    'actual_nvp_model_read': False,
    'compiled_read_capacity_response_verified': True,
    'read_capacity_report_sha256': hashlib.sha256(capacity_raw).hexdigest(),
    'compiled_read_write_lba_shift': 11,
    'compiled_read_write_block_bytes': 2048,
    'instruction_evidence': [
        {'text_offset': hex(offset), 'arm_word': hex(word), 'meaning': description}
        for offset, (word, description) in instructions.items()
    ],
    'device_access_performed': False,
    'limits': [
        'Stock script configuration, not observation of a running kernel.',
        'USB exposed capacity does not measure the Linux root partition.',
        'Read/write conversion and bounded READ CAPACITY construction are verified; command validation and physical USB transport are not.',
    ],
}
(ROOT / 'sources/native-usb-export-mapping.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
