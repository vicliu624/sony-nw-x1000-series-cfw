"""Static inventory of pinned JP firmware music import/tag interfaces; no device IO."""
from pathlib import Path
import hashlib
import io
import json
import re
import tarfile
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
packed=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
strings=re.compile(rb'[\x20-\x7e]{4,}')
pattern=re.compile(r'/contents|\bMUSIC\b|ID3|APIC|TIT2|TPE1|TALB|TRCK|music.?db|rescan|scan.?music|rebuild|update.?database|create.?database|metadata|OMGAUDIO',re.I)
symbol_pattern=re.compile(r'id3|metadata|tag_|database|dbscan|rescan|scan.*(file|dir|content)|import|rebuild|MomaClient|MomaMediaObject',re.I)
rows=[]
with tarfile.open(packed,'r|gz') as archive:
    for member in archive:
        if not member.isfile(): continue
        data=archive.extractfile(member).read()
        if not data.startswith(b'\x7fELF'): continue
        elf=ELFFile(io.BytesIO(data));sym=elf.get_section_by_name('.dynsym')
        exports=[s.name for s in sym.iter_symbols() if s['st_shndx']!='SHN_UNDEF' and symbol_pattern.search(s.name)] if sym else []
        hits=[]
        for match in strings.finditer(data):
            value=match.group().decode('ascii')
            if not pattern.search(value): continue
            address=None
            for segment in elf.iter_segments():
                if segment['p_type']=='PT_LOAD' and segment['p_offset']<=match.start()<segment['p_offset']+segment['p_filesz']:
                    address=hex(segment['p_vaddr']+match.start()-segment['p_offset']);break
            hits.append({'offset':hex(match.start()),'address':address,'text':value[:512]})
        wide=[]
        for match in re.finditer(rb'(?:[\x20-\x7e]\x00){4,}',data):
            value=match.group().decode('utf-16le')
            if re.search(r'/contents|^/?MUSIC/?$|OMGAUDIO|^APIC$|^TIT2$|^TPE1$|^TALB$',value,re.I):
                wide.append({'offset':hex(match.start()),'text':value[:512]})
        if hits or exports:
            rows.append({'path':member.name,'sha256':hashlib.sha256(data).hexdigest(),'strings':hits,'wide_strings':wide,'exports':exports})
report={'scope':'static strings/dynamic symbol inventory only','device_access':False,'ready_to_flash':False,
        'archive_sha256':hashlib.sha256(packed.read_bytes()).hexdigest(),'files':rows,
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['Strings/exports do not prove callability, supported paths, tag compatibility or database refresh.','No imported content, device scan or stock parser execution.']}
(ROOT/'sources/native-stock-music-import-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
for row in rows:
    print(row['path'],len(row['strings']),'strings',len(row['exports']),'exports')
    for hit in row['strings'][:12]: print(' ',hit['address'],hit['text'])
    if row['exports']: print(' ',row['exports'][:20])
