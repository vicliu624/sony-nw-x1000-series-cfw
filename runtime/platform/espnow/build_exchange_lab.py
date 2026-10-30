"""Prepare finite native over-air acceptance worker, never deploy or run it."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'work/espnow-exchange-lab';OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['.venv/bin/python','runtime/platform/espnow/build_stock_reload_lab.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
candidate=ROOT/'work/espnow-radio-candidate-poll-filter'
review=json.loads((candidate/'review.json').read_text())
records=[]
for name in ('sd8686.bin','helper_sd.bin'):
    path=candidate/'candidate'/name;blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
    expected=review['candidate_sha256'] if name=='sd8686.bin' else 'b0157d1f4518e806c0bc5128ab302a7f97d78ee34b84cb41cb4f2bbbb2a00e6d'
    if digest!=expected:raise ValueError('unqualified radio input')
    records.append({'path':'/contents/HOMEBREW/data/espnow/candidate/'+name,'bytes':len(blob),'sha256':digest})
header=['static const struct stock_input exchange_inputs[]={']
for r in records:header.append('{'+json.dumps(r['path'])+','+str(r['bytes'])+',{'+','.join(str(b) for b in bytes.fromhex(r['sha256']))+'}},')
(OUT/'exchange_inputs.h').write_text('\n'.join(header+['};'])+'\n')
version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip()
SDK=ROOT/'work/espnow-native-library'/version/'sdk'
LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
sources=['runtime/platform/espnow/exchange_lab.c','runtime/store/start.c','runtime/store/start.S']
app=OUT/'exchange-lab.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
    '-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
    '-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E',
    '-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),'-I'+str(ROOT/'work/espnow-stock-reload-lab'),
    *sources,str(SDK/'lib/libxnow.a'),str(STOCK/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0'),
    str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',
    f'{LIB}:{STOCK}:{RESOLVER}',str(app),'--help'],capture_output=True,text=True,check=True,timeout=15)
report={'built':True,'version':'0.1.0-dev.1','library_version':version,'bytes':app.stat().st_size,
    'sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'md5':hashlib.md5(app.read_bytes()).hexdigest(),
    'candidate_inputs':records,'help_smoke':run.stdout,
    'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,
        'runtime/platform/espnow/stock_reload_lab.c','runtime/platform/espnow/stock_wifi_session.c',
        'runtime/platform/espnow/build_exchange_lab.py']},
    'library_build':json.loads((SDK/'build.json').read_text()),
    'physical_exchange_qualified':False,'device_written':False,'radio_loaded':False}
(OUT/'build.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k in ('built','version','library_version','bytes','sha256','help_smoke')},indent=2))
