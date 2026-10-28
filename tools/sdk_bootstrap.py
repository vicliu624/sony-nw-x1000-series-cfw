"""Prepare only hash-pinned SDK libc/loader inputs; never runs Sony's updater."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
from app_registry import ROOT
from sdk_build import LIBRARIES

def setup(stock_exe=None):
    definition=json.loads((ROOT/'sources/downloads.json').read_text())[0]
    original=Path(stock_exe).resolve() if stock_exe else ROOT/definition['path']
    if stock_exe is None and not original.exists():
        original.parent.mkdir(parents=True,exist_ok=True)
        request=urllib.request.Request(definition['url'],headers={'User-Agent':'X1000-SDK/0.1'})
        with urllib.request.urlopen(request,timeout=60) as response:data=response.read(definition['bytes']+1)
        if len(data)!=definition['bytes'] or hashlib.sha256(data).hexdigest()!=definition['sha256']:
            raise ValueError('Downloaded updater hash/size mismatch')
        partial=original.with_suffix('.sdk.partial');partial.write_bytes(data);partial.replace(original)
    if hashlib.sha256(original.read_bytes()).hexdigest()!=definition['sha256']:
        raise ValueError('Use the exact Japanese1.11 updater recorded in sources/downloads.json')
    packed=subprocess.check_output(['7z','x','-so',str(original),'/NW_WM_FW.UPG'])
    sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
    _,parts=unpack(packed)
    lib=ROOT/'work/arm-signal-tests/lib';lib.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
        for name,digest in LIBRARIES.items():
            member=archive.getmember('./lib/'+name)
            if member.issym():
                target=member.linkname
                if '/' in target or target.startswith('.'): raise ValueError('Unsafe library alias')
                member=archive.getmember('./lib/'+target)
            if not member.isfile(): raise ValueError('Invalid library entry')
            data=archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest()!=digest: raise ValueError('Stock library mismatch')
            path=lib/name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:
                path.chmod(0o755);continue
            if path.is_symlink(): raise ValueError('Unexpected stock library link; preserve inputs and select a clean checkout')
            path.write_bytes(data);path.chmod(0o755)
    print('Pinned libc and loader ready. No updater executed, firmware built or device accessed.')
