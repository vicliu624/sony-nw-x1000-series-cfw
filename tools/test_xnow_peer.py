"""Host sanitizers and actual ARM926/old-Sony-libc wire-code execution only."""
from pathlib import Path
import hashlib,json,subprocess
from app_registry import ROOT
OUT=ROOT/'work/espnow-peer-tests';OUT.mkdir(parents=True,exist_ok=True)
sources=['tools/test_xnow_peer.c','runtime/platform/espnow/xnow_peer.c']
host=OUT/'wire.host'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*sources,'-o',str(host)],cwd=ROOT,check=True)
native=subprocess.run([str(host)],capture_output=True,text=True,timeout=30,check=True)
LIB=ROOT/'work/arm-signal-tests/lib';arm=OUT/'wire.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE',
    '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft',
    '-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv',
    '-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',
    str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
target=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',str(LIB),str(arm)],capture_output=True,text=True,timeout=60,check=True)
report={'passed':True,'host_asan_ubsan':native.stdout,'arm926_stock_libc':target.stdout,
    'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_peer.h']},
    'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'radio_transport_changed':False,'over_air_tested':False,'device_accessed':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
