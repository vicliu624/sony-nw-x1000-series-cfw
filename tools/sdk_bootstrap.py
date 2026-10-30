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

SERVICE_LIBRARIES={
    'libcnmgr.so.1':'688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1',
    'libcares.so.2':'87080fcca3ee009ded018c82f9a598f9515b97b0ec07c79f952eae330f76a8f4',
    'librt.so.1':'be0149f8297952ba0dc9ea7aa98f0e2f9d21b6f697af22bf7c1ef776823dba22',
    'libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474',
    'libm.so.6':'b3aa1ce9b9770fdd447c5c5190f5956d4a6556ecc793d2e36230d11f29e90283',
}

def fetch_pinned(url,path,digest,limit=16777216):
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:return path
    request=urllib.request.Request(url,headers={'User-Agent':'X1000-SDK-services/0.2'})
    with urllib.request.urlopen(request,timeout=60) as response:data=response.read(limit+1)
    if len(data)>limit or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('SDK dependency hash mismatch: '+url)
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.partial')
    temporary.write_bytes(data);temporary.replace(path);return path

def setup(stock_exe=None,services=False):
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
        targets={name:(lib,digest) for name,digest in LIBRARIES.items()}
        if services:targets.update({name:(ROOT/'work/stock-resolver-probe',digest) for name,digest in SERVICE_LIBRARIES.items()})
        for name,(destination,digest) in targets.items():
            candidates=[path for path in ('./lib/'+name,'./usr/lib/'+name) if path in archive.getnames()]
            if len(candidates)!=1:raise ValueError('Cannot identify unique stock library: '+name)
            member=archive.getmember(candidates[0])
            if member.issym():
                target=member.linkname
                if '/' in target or target.startswith('.'): raise ValueError('Unsafe library alias')
                member=archive.getmember(member.name.rsplit('/',1)[0]+'/'+target)
            if not member.isfile(): raise ValueError('Invalid library entry')
            data=archive.extractfile(member).read()
            if hashlib.sha256(data).hexdigest()!=digest: raise ValueError('Stock library mismatch')
            destination.mkdir(parents=True,exist_ok=True);path=destination/name
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:
                path.chmod(0o755);continue
            if path.is_symlink(): raise ValueError('Unexpected stock library link; preserve inputs and select a clean checkout')
            path.write_bytes(data);path.chmod(0o755)
    if services:
        ares=fetch_pinned('https://raw.githubusercontent.com/c-ares/c-ares/cares-1_5_2/ares.h',ROOT/'work/stock-resolver-probe/ares.h','ed0804876d9dc6846acd30165ccc5a866cd7e6987aa5907adb53130dc3868f04')
        packed=fetch_pinned('https://www.bearssl.org/bearssl-0.6.tar.gz',ROOT/'work/bearssl-0.6.tar.gz','6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14')
        crypto=ROOT/'work/external-tls-probe';crypto.mkdir(parents=True,exist_ok=True)
        with tarfile.open(packed) as archive:archive.extractall(crypto,filter='data')
        subprocess.run(['make','-C',str(crypto/'bearssl-0.6'),'-j2','lib','CC=arm-linux-gnueabi-gcc','AR=arm-linux-gnueabi-ar',
                        'CFLAGS=-Os -march=armv5te -marm -mfloat-abi=soft -ffreestanding -fno-builtin -DBR_USE_URANDOM=0','BUILD='+str(crypto/'arm-build')],check=True,stdout=subprocess.DEVNULL)
    print('Pinned libc and loader ready. No updater executed, firmware built or device accessed.')
