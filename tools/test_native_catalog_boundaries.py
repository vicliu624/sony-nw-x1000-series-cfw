"""Compare host catalog acceptance with a selected stock-libc ARM launcher."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from actual_app_fixture import stock_libc
from component_receipts import ROOT, digest, private
from store_test_fixture import workspace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--launcher', required=True, type=Path)
launcher = private(parser.parse_args().launcher)
launcher_sha256 = digest(launcher)
library = stock_libc()
sys.path.insert(0, str(ROOT / 'runtime'))
from catalog import read_app

program=bytearray(96);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
def make(name='Demo',version='0.1.0',size=None):
 fields={'api':'1','id':'demo','name':name,'version':version,'target':'sony-nw-x1000-jp','exec':'app','bytes':'96','sha256':hashlib.sha256(program).hexdigest()}
 raw=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode()
 if size:raw=raw.replace(b'bytes=96',b'bytes='+b'0'*(size-len(raw))+b'96');assert len(raw)==size
 return raw
cases=[('name48',make('a'*48),True),('name49',make('a'*49),False),('utf8-name48',make('中'*16),True),('utf8-name51',make('中'*17),False),('version32',make(version='0.1.0-'+'a'*26),True),('version33',make(version='0.1.0-'+'a'*27),False),('manifest1024',make(size=1024),True),('manifest1025',make(size=1025),False)]
cases.extend([('windows-CRLF',make().replace(b'\n',b'\r\n'),True),('bare-CR',make().replace(b'\n',b'\r'),False)])

rows = []
with workspace('catalog-boundaries-') as folder:
    apps = Path(folder) / 'apps'
    app = apps / 'demo'
    app.mkdir(parents=True)
    (app / 'app').write_bytes(program)
    for name, data, expected in cases:
        (app / 'app.ini').write_bytes(data)
        checked = subprocess.run([
            'qemu-arm', '-cpu', 'arm926', str(library / 'ld-linux.so.3'), '--library-path',
            str(library), str(launcher), '--catalog', str(apps),
        ], capture_output=True, text=True, cwd=ROOT, timeout=10)
        try:
            read_app(app)
            host_ok = True
        except ValueError:
            host_ok = False
        arm_ok = checked.returncode == 0 and checked.stdout.startswith('demo\t')
        assert arm_ok == host_ok == expected, (name, checked.returncode, checked.stdout, checked.stderr, host_ok)
        if not expected:
            assert checked.returncode == 1 and not checked.stdout, (name, checked)
        rows.append(dict(case=name, manifest_bytes=len(data), ARM_accepts=arm_ok, host_accepts=host_ok))

assert digest(launcher) == launcher_sha256
print(json.dumps(dict(all_passed=True, physical_device_access=False,
                      launcher=launcher.relative_to(ROOT).as_posix(), launcher_sha256=launcher_sha256,
                      host_catalog_sha256=digest(ROOT / 'runtime/catalog.py'), cases=rows,
                      limits=['Original-libc ARM userspace replay with ordinary local files.',
                              'Synthetic program bytes are parsed and never executed.']), indent=2))
