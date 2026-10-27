"""Read every regular ELF in the pinned stock rootfs; never extract or execute."""
from pathlib import Path
import hashlib, io, json, tarfile
from elftools.elf.elffile import ELFFile

root = Path(__file__).resolve().parents[1]
archive = root / 'work/upg-jp/verified-3.bin'
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
rows = []
with tarfile.open(archive, 'r:*') as tar:
    for member in tar:
        if not member.isfile():
            continue
        f = tar.extractfile(member)
        prefix = f.read(4)
        if prefix != b'\x7fELF':
            continue
        raw = prefix + f.read()
        elf = ELFFile(io.BytesIO(raw))
        symbols = elf.get_section_by_name('.dynsym')
        imports = sorted({s.name for s in symbols.iter_symbols() if s['st_shndx'] == 'SHN_UNDEF' and s.name}) if symbols else []
        dynamic = elf.get_section_by_name('.dynamic')
        needed = [t.needed for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_NEEDED'] if dynamic else []
        rows.append({'path': member.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                     'needed': needed, 'cnmgr_imports': [s for s in imports if s.startswith('cnmgr_')],
                     'content_network_imports': [s for s in imports if s.startswith(('salc_curl_', 'yal_', 'curl_'))]})
report = {'rootfs_sha256': digest, 'elf_count': len(rows), 'elf_inventory': rows,
          'limits': ['Static dynamic-import inventory only; no application activation or runtime reachability proven.',
                     'No direct import does not exclude indirect, dynamically resolved or IPC-based network use.']}
(root / 'sources/stock-wifi-client-inventory.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'elf_count': len(rows), 'direct_cnmgr_clients': [r['path'] for r in rows if r['cnmgr_imports']],
                  'content_network_clients': [r['path'] for r in rows if r['content_network_imports']]}, indent=2))
