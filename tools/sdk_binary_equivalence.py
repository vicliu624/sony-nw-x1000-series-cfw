"""Strict comparison with one known GCC build-noise exception, in memory only.

Never edits executables/inventories or relaxes publication integrity checks.
"""
import hashlib
import io
from pathlib import Path
import re
from elftools.elf.elffile import ELFFile

def normalize_gcc_file_symbols(data):
    if not data.startswith(b'\x7fELF'):return data,[]
    elf=ELFFile(io.BytesIO(data));output=bytearray(data);changes=[]
    symbols=elf.get_section_by_name('.symtab')
    if symbols is None:return data,changes
    strings=elf.get_section(symbols['sh_link'])
    if strings['sh_flags']&2:raise ValueError('Symbol-name table is runtime allocated; cannot normalize')
    entries=list(symbols.iter_symbols())
    for symbol in entries:
        name=symbol.name
        if symbol['st_info']['type']!='STT_FILE' or not re.fullmatch(r'cc[A-Za-z0-9]{6}\.o',name):continue
        start=symbol['st_name'];end=start+len(name)
        if any(other['st_info']['type']!='STT_FILE' and start<=other['st_name']<end for other in entries):
            raise ValueError('GCC file marker shares bytes with a program symbol')
        offset=strings['sh_offset']+start
        if data[offset:offset+len(name)+1]!=name.encode()+b'\0':raise ValueError('Malformed temporary file symbol')
        output[offset:offset+len(name)]=b'cc000000.o'
        changes.append({'section':strings.name,'type':'STT_FILE','name':name,'replacement':'cc000000.o'})
    return bytes(output),changes

def canonical_payload(folder):
    """Compare all payload bytes, with digest edges following normalized ELFs.

    Raw hashes/inventory remain separately validated by verify_app_package.
    No field, path, version, size, code/data or other symbol name is dropped.
    """
    folder=Path(folder);raw={p.relative_to(folder).as_posix():p.read_bytes() for p in sorted(folder.rglob('*')) if p.is_file()}
    canonical={};changes={}
    for name,data in raw.items():
        canonical[name],records=normalize_gcc_file_symbols(data)
        if records:changes[name]=records
    if 'app.ini' in raw:
        before=hashlib.sha256(raw['app']).hexdigest().encode();after=hashlib.sha256(canonical['app']).hexdigest().encode()
        expected=b'sha256='+before
        if raw['app.ini'].count(expected)!=1:raise ValueError('Executable identity edge missing/ambiguous')
        canonical['app.ini']=raw['app.ini'].replace(expected,b'sha256='+after)
    if 'files.sha256' in raw:
        lines=raw['files.sha256'].splitlines(keepends=True)
        for i,line in enumerate(lines[1:],1):
            parts=line.split(b' ',2)
            if len(parts)!=3:raise ValueError('Malformed raw inventory')
            name=parts[2].rstrip(b'\r\n').decode('ascii')
            if name not in canonical:raise ValueError('Inventory points outside package')
            lines[i]=hashlib.sha256(canonical[name]).hexdigest().encode()+line[64:]
        canonical['files.sha256']=b''.join(lines)
    return {name:hashlib.sha256(data).hexdigest() for name,data in canonical.items()},changes
