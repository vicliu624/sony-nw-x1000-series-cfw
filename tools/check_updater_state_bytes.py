"""PC-only byte audit of the statically inspected Sony updater; never executes it."""
import hashlib, json, struct
from pathlib import Path
root = Path(__file__).resolve().parents[1]
p = root / 'work/updater-static-review-1/extracted/FWUpdater.exe'
b = p.read_bytes()
expected = '3cf7eb2e354d2e6d3f0cddd06ab67755696579a0d2cc85b68672ecc44ccb3c1c'
if hashlib.sha256(b).hexdigest() != expected:
    raise SystemExit('Unexpected updater input')
# These reviewed addresses belong to .text, whose RVA equals file offset.
def at(va, n):
    if not 0x401000 <= va < 0x41c000 or va+n > 0x41c000:
        raise ValueError('Outside reviewed text mapping')
    return b[va-0x400000:va-0x400000+n]
checks = {
    'same_version_resource_203': (0x40799c, 'b8cb000000'),
    'state_loop_consumes_result': (0x406ae1, '8bf083feff'),
    'confirmation_wrapper_call': (0x406a78, 'e833c4ffff'),
}
for name,(va,hexbytes) in checks.items():
    if at(va,len(bytes.fromhex(hexbytes))) != bytes.fromhex(hexbytes):
        raise SystemExit('Byte mismatch: '+name)
entries = struct.unpack('<7I',at(0x406b0c,28))
if entries != (0x406a78,0x406a7f,0x406a8f,0x406a96,0x406a9d,0x406ab4,0x406acb):
    raise SystemExit('State table mismatch')
print(json.dumps({'input_sha256':expected,'instruction_checks':list(checks),
                  'states':{str(i+3):hex(v) for i,v in enumerate(entries)},
                  'scope':'Static bytes only; no updater or device execution'},indent=2))

