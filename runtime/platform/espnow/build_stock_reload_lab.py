"""Build an explicit stock-only driver recovery lab. No device/network IO."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'work/espnow-stock-reload-lab';OUT.mkdir(parents=True,exist_ok=True)
IMAGE=ROOT/'work/upg-jp/verified-3.bin'
if hashlib.sha256(IMAGE.read_bytes()).hexdigest()!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':
    raise ValueError('unqualified original rootfs')
paths=['/bin/busybox','/usr/local/bin/wlan_load_driver.sh','/usr/local/bin/wlanapi.sh',
       '/usr/local/bin/nvp','/usr/local/bin/iwpriv','/usr/local/bin/iwconfig','/usr/local/bin/wlanconfig',
       '/etc/hostcmd.conf',*['/lib/modules/'+s for s in ('sd8686.ko','mp200_sdio.ko',
       'wlan_pm_register.ko','wlan_pwr_ctrl.ko','sd8686.bin','helper_sd.bin')]]
links=['/bin/sh','/bin/grep','/sbin/insmod','/sbin/rmmod','/sbin/lsmod']
records=[];aliases=[]
with tarfile.open(IMAGE,'r:gz') as tar:
    members={m.name.lstrip('./'):m for m in tar.getmembers()}
    if 'usr/local/bin/wlanapi.inc' in members:raise ValueError('unexpected optional override')
    for path in paths:
        m=members[path[1:]]
        if not m.isfile() or not 0<m.size<=1048576:raise ValueError(path)
        blob=tar.extractfile(m).read()
        records.append({'path':path,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
    for path in links:
        m=members[path[1:]]
        if not m.issym():raise ValueError(path)
        aliases.append({'path':path,'target':m.linkname})
header=['struct stock_input {const char *path;unsigned bytes;unsigned char sha[32];};',
        'static const struct stock_input stock_inputs[]={']
for r in records:
    header.append('{'+json.dumps(r['path'])+','+str(r['bytes'])+',{'+','.join(str(b) for b in bytes.fromhex(r['sha256']))+'}},')
header+=['};','struct stock_link {const char *path,*target;};','static const struct stock_link stock_links[]={']
header += ['{'+json.dumps(r['path'])+','+json.dumps(r['target'])+'},' for r in aliases]
header+=['};'];(OUT/'stock_reload_inputs.h').write_text('\n'.join(header)+'\n')
subprocess.run(['.venv/bin/python','runtime/platform/espnow/build_library.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip()
SDK=ROOT/'work/espnow-native-library'/version/'sdk'
LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
sources=['runtime/platform/espnow/stock_reload_lab.c','runtime/store/start.c','runtime/store/start.S']
app=OUT/'stock-reload-lab.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
    '-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
    '-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E',
    '-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),*sources,
    str(SDK/'lib/libxnow.a'),str(STOCK/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0'),
    str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',
    f'{LIB}:{STOCK}:{RESOLVER}',str(app),'--help'],capture_output=True,text=True,check=True,timeout=15)
report={'built':True,'version':'0.1.0-dev.1','library_version':version,'bytes':app.stat().st_size,
    'sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'md5':hashlib.md5(app.read_bytes()).hexdigest(),
    'original_root_inputs':records,'original_symlinks':aliases,'help_smoke':run.stdout,
    'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in
        [*sources,'runtime/platform/espnow/stock_wifi_session.c','runtime/platform/espnow/build_stock_reload_lab.py']},
    'library_build':json.loads((SDK/'build.json').read_text()),
    'physical_reload_qualified':False,'device_written':False}
(OUT/'build.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k in ('built','version','library_version','bytes','sha256','md5','help_smoke')},indent=2))
