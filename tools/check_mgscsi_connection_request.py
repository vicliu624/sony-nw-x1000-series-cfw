"""Resolve the stock mgscsi connection ioctl using literals and ELF relocations."""
from pathlib import Path
import hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
    module = tar.extractfile('./lib/modules/mgscsi.ko').read()
elf = ELFFile(io.BytesIO(module))
symbols = elf.get_section_by_name('.symtab')
code = elf.get_section_by_name('.text').data()
relocs = {r['r_offset']: r for r in elf.get_section_by_name('.rel.text').iter_relocations()}
word = lambda offset: struct.unpack_from('<I', code, offset)[0]
def target_symbol(offset):
    symbol = symbols.get_symbol(relocs[offset]['r_info_sym'])
    if symbol['st_info']['type'] == 'STT_SECTION':
        return elf.get_section(symbol['st_shndx']).name
    return symbol.name
assert word(0x5fc) == 0x40017325
assert word(0x24c) == 0xe59f33a8  # PC+8+0x3a8 -> literal5fc
assert word(0x250) == 0xe1510003  # compare complete ioctl, not only request number
assert word(0x254) == 0x0a000173 and target_symbol(0x254) == '.text'
assert ((word(0x254) & 0xffffff) << 2) + 8 == 0x5d4
assert word(0x5d4) == 0xe20000ff  # byte-valued argument
assert target_symbol(0x5d8) == 'mgscsi_ioctl_set_conn_status'
assert target_symbol(0x1690) == 'mgscsiMgCtrlInit'
assert target_symbol(0x16a0) == 'mgscsiAuthInit'
symbol = next(s for s in symbols.iter_symbols() if s.name == 'mgscsi_ioctl_set_conn_status')
assert symbol['st_value'] == 0x1684 and symbol['st_size'] == 48
report = {
    'module_sha256': hashlib.sha256(module).hexdigest(),
    'ioctl': '0x40017325', 'argument_mask': '0xff',
    'handler': {'symbol': symbol.name, 'text_offset': hex(symbol['st_value'])},
    'direct_calls': ['mgscsiMgCtrlInit', 'mgscsiAuthInit'],
    'route_verified_by': ['literal5fc', 'compare250', 'conditional-branch254 relocation', 'call5d8 relocation'],
    'physical_device_access': False,
    'limits': ['Static route and direct calls only; initialization internals and hardware effects not fully traced.',
               'This request alone is not proof of enabling USB disk export.'],
}
(ROOT / 'sources/native-mgscsi-connection-request.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
