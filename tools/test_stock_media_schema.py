"""Execute the pinned original local-catalog schema registration offline."""
import hashlib
import io
import json
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from app_registry import ROOT

raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
image = ELFFile(io.BytesIO(raw))
cases = []
for scenario in ('success', 'already-registered', 'group-error', 'property-error'):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for segment in image.iter_segments():
        if segment['p_type'] != 'PT_LOAD':
            continue
        address = int(segment['p_vaddr'])
        base = address & ~4095
        cpu.mem_map(base, (address-base+int(segment['p_memsz'])+4095) & ~4095)
        cpu.mem_write(address, segment.data())
    area = 0x71000000
    cpu.mem_map(area, 65536)
    done = area + 0xff00
    rows = []
    finalized = []

    def hook(u, address, size, data):
        if address == done:
            u.emu_stop()
            return
        if address not in (0x2a1134, 0x2a1190, 0x2a13c8):
            return
        args = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        assert args[0] == area
        result = 0
        if address == 0x2a13c8:
            finalized.append(args[1:3])
        else:
            name = bytes(u.mem_read(args[3], 128)).split(b'\0', 1)[0].decode('ascii')
            rows.append(dict(kind='group' if address == 0x2a1134 else 'property', id=args[1], scalar=chr(args[2]), name=name))
            if scenario == 'already-registered':
                result = 0x2113
            elif scenario == 'group-error' and address == 0x2a1134:
                result = 0x2204
            elif scenario == 'property-error' and address == 0x2a1190:
                result = 0x2204
        u.reg_write(UC_ARM_REG_R0, result)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.reg_write(UC_ARM_REG_R0, area)
    cpu.reg_write(UC_ARM_REG_SP, area + 0xf000)
    cpu.reg_write(UC_ARM_REG_LR, done)
    cpu.emu_start(0x2997fc, done+4, count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC) == done
    if scenario in ('success', 'already-registered'):
        assert len(rows) == 56 and finalized == [[0x80, 10]]
        props = {row['name']: row for row in rows if row['kind'] == 'property'}
        for name, key, scalar in (('MTP_FORMAT', 0x27, 'h'), ('AUDIOCODEC', 0x29, 'I'), ('AADPLAYLISTID', 0x31, 's')):
            assert (props[name]['id'], props[name]['scalar']) == (key, scalar)
        assert len(props) == 50
    else:
        assert len(rows) == (1 if scenario == 'group-error' else 7)
        assert not finalized
    cases.append(dict(scenario=scenario, registrations=len(rows), finalized=bool(finalized)))
output = ROOT / 'work/player-stock-media-schema'
output.mkdir(parents=True, exist_ok=True)
report = dict(target_sha256=hashlib.sha256(raw).hexdigest(), cases=cases,
              limits=['Original registration-loop instructions execute; registration callees are modeled.',
                      'Local schema property IDs are not generic MOMA metadata keys.',
                      'This does not establish FORMAT3 playlist semantics or device database contents.'])
report['source_sha256'] = hashlib.sha256((ROOT/'tools/test_stock_media_schema.py').read_bytes()).hexdigest()
(output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
