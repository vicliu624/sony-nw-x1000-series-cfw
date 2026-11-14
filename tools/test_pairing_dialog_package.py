"""Verify packaged unlink wording and native dialog-factory routing."""
import argparse
import io
import json
import re
import struct
import sys
import tarfile

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

from app_registry import ROOT
from remote_choice_resource import CONFIRM_TARGET,PAIR_TARGET
from review_managed_remote_profile import digest, receipt

sys.path.insert(0, str(ROOT / 'scripts'))
from resources import parse_stx
from upg import unpack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-review', required=True)
    args = parser.parse_args()
    path, review = receipt(args.firmware_review)
    upg = ROOT / review['artifact']
    assert digest(upg) == review['sha256']
    root = path.parent / 'rockbox-check/part-3.bin'
    assert root.read_bytes() == unpack(upg.read_bytes(), require_stock=False)[1][3]
    with tarfile.open(root, 'r:gz') as archive:
        resource = archive.extractfile('./' + CONFIRM_TARGET).read()
        rows = dict(re.findall(rb'^tid\.(\d+):\s*"tid-(\d+)"', resource, re.M))
        assert rows == {b'0': b'3051', b'40': b'0000', b'41': b'0001'}
        assert b'"sid-139-03"' in resource
        pair_resource=archive.extractfile('./'+PAIR_TARGET).read()
        assert b'"sid-139-04"' in pair_resource
        assert dict(re.findall(rb'^tid\.(\d+):\s*"tid-(\d+)"',pair_resource,re.M))=={b'0':b'3014',b'40':b'0000',b'41':b'0001'}
        languages = []
        prefix = './usr/local/share/gemini/res/stx/ucs2-dev-'
        for name in archive.getnames():
            if name.startswith(prefix) and name.endswith('.stx'):
                texts = parse_stx(archive.extractfile(name).read())
                assert all(texts[i] for i in (3051,3014,0,1)) and texts[0] != texts[1]
                languages.append(name[len(prefix):-4])
        raw = archive.extractfile('./usr/local/lib/x1000-player/SpiderApp').read()
    assert len(languages) == 11

    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    cpu.mem_map(0x8000, 0x1000000)
    cpu.mem_map(0x70000000, 0x10000)
    for segment in ELFFile(io.BytesIO(raw)).iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            cpu.mem_write(segment['p_vaddr'], segment.data())
    descriptor = 0x4eb99c + 43 * 48
    before = struct.unpack('<12I', cpu.mem_read(descriptor, 48))
    assert before == (43, 14400, 3, 0, 0, 0, 0, 2, 0, 0, 0, 4)
    cpu.mem_write(descriptor + 4, struct.pack('<I', 13903))
    control, window, stop = 0x70001000, 0x70003000, 0x7000ff00
    routed = []

    def hook(uc, address, size, _):
        if address == 0xe87f4:
            result = 0
        elif address == 0xe9300:
            result = window
        elif address == 0xc6e7c:
            assert uc.reg_read(UC_ARM_REG_R0) == control
            assert struct.unpack('<I', uc.mem_read(control + 32, 4))[0] == descriptor
            words = struct.unpack('<12I', uc.mem_read(descriptor, 48))
            assert words == (43, 13903, *before[2:])
            routed.append(address)
            result = 0
        else:
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.reg_write(UC_ARM_REG_R0, control)
    cpu.reg_write(UC_ARM_REG_R1, descriptor)
    cpu.reg_write(UC_ARM_REG_SP, 0x7000f000)
    cpu.reg_write(UC_ARM_REG_LR, stop)
    cpu.emu_start(0xc6880, stop, count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC) == stop and routed == [0xc6e7c]
    print(json.dumps(dict(passed=True, candidate_sha256=review['sha256'], languages=sorted(languages),
                          native_confirmation_factory=True, rendering_modeled=True, device_accessed=False), indent=2))


if __name__ == '__main__':
    main()
