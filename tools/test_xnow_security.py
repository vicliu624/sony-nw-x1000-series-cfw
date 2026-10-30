"""Independent PyCryptodome reference vs BearSSL C CCMP, host and stock ARM."""
from pathlib import Path
import hashlib,json,subprocess
from app_registry import ROOT
OUT=ROOT/'work/espnow-security-tests';OUT.mkdir(exist_ok=True)
B=ROOT/'work/external-tls-probe/bearssl-0.6';hostlib=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a';armlib=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
sources=['tools/test_xnow_security.c','runtime/platform/espnow/xnow_security.c','runtime/platform/espnow/xnow_ccmp.c','runtime/platform/espnow/xnow_pn.c','runtime/platform/espnow/xnow_wire.c','runtime/native/sha256.c'];include=['-I',str(B/'inc'),'-I',str(OUT)]
host=OUT/'ccmp.host';subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*include,*sources,str(hostlib),'-o',str(host)],cwd=ROOT,check=True)
a=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=30)
lib=ROOT/'work/arm-signal-tests/lib';arm=OUT/'ccmp.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*include,*sources,'runtime/store/start.c','runtime/store/start.S',str(armlib),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
b=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,check=True,timeout=60)
report={'passed':True,'storage_callbacks_modeled':True,'host_asan_ubsan':a.stdout,'arm926_stock_libc':b.stdout,'physical_espnow_encryption_verified':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_ccmp.h','runtime/platform/espnow/xnow_security.h','runtime/platform/espnow/xnow_pn.h','runtime/platform/espnow/xnow_wire.h','tools/test_xnow_security.py']},'bearssl_archives':{'host':hashlib.sha256(hostlib.read_bytes()).hexdigest(),'arm':hashlib.sha256(armlib.read_bytes()).hexdigest()}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
