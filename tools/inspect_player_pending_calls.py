"""Inventory direct ARM pending-tracker callers in the pinned player, PC only.

These are encoded branch candidates, not proof that every site is reachable.
Indirect calls and data interpreted as instructions require separate analysis.
"""
import hashlib
import io
import json
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from app_registry import ROOT


def main():
    raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85':
        raise ValueError('Pinned Japanese 1.11 SpiderApp required')
    decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    decoder.skipdata = True
    targets = {0x48a14: 'append', 0x48a78: 'remove', 0x11250: 'complete',
               0x275dcc: 'ctrlinfo-pool-finalize',
               0x275c20: 'met-finalizer-candidate'}
    calls = []
    references = []
    for segment in ELFFile(io.BytesIO(raw)).iter_segments():
        if segment['p_type'] != 'PT_LOAD':
            continue
        data = segment.data()
        base = int(segment['p_vaddr'])
        for offset in range(0, len(data) - 3, 4):
            word = struct.unpack_from('<I', data, offset)[0]
            if word in targets:
                start = max(0, offset - 16)
                end = min(len(data) & ~3, offset + 20)
                references.append(dict(address=hex(base + offset), target=hex(word),
                                       operation=targets[word],
                                       segment_executable=bool(segment['p_flags'] & 1),
                                       surrounding_words=[hex(v[0]) for v in struct.iter_unpack('<I', data[start:end])]))
            if not segment['p_flags'] & 1:
                continue
            # Include conditional direct B/BL, including tail-call thunks.
            # BLX/indirect branches are not covered.
            if word & 0x0e000000 != 0x0a000000 or word >> 28 == 15:
                continue
            address = base + offset
            target = address + 8 + (((word & 0xffffff) ^ 0x800000) - 0x800000) * 4
            if target not in targets:
                continue
            start = max(0, offset - 48)
            context = [dict(address=hex(i.address), instruction=i.mnemonic + ' ' + i.op_str)
                       for i in decoder.disasm(data[start:offset + 12], base + start)]
            calls.append(dict(address=hex(address), target=hex(target),
                              link=bool(word & 0x01000000),
                              operation=targets[target], context=context))
    report = dict(stock_sha256=digest, device_accessed=False, direct_branch_candidates=calls,
                  literal_address_candidates=references,
                  limits=['No indirect-call or reachability proof.',
                          'Literal address matches are candidates, not proven function-pointer dispatch.',
                          'No SDK token namespace, capacity or installation approval.'])
    output = ROOT / 'work/player-pending-calls/report.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([dict(address=c['address'], target=c['target'], operation=c['operation']) for c in calls], indent=2))


if __name__ == '__main__':
    main()
