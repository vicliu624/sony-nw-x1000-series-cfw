"""Native identity schema and fresh login entropy; no account credentials."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-identity';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
core=['runtime/apps/qqmusic/qqmusic_identity.c','runtime/apps/qqmusic/qqmusic_cgi.c','runtime/apps/qqmusic/qqmusic_json.c','runtime/apps/qqmusic/qqmusic_protocol.c','runtime/apps/qqmusic/qqmusic_session.c','runtime/store/tls_platform.c','runtime/store/https_url.c','tools/fixtures/qqmusic_identity.c']
flags=['-std=c99','-Wall','-Wextra','-Werror']
host=work/'identity-tests.sanitized'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=20)
lib=ROOT/'work/arm-signal-tests/lib';arm=work/'identity-tests.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],cwd=ROOT,check=True,timeout=20)
report={'passed':True,'scope':'native_identity_material','device_tested':False,'checks':['explicit identity configuration','fresh state and ui per attempt','seed failure clears output','zero and ff entropy reject','repeated entropy reject','stop before and during seed','account fields and invalid guid reject','missing identity reject','actual urandom default','identity clear disables prepare'], 'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['runtime/apps/qqmusic/qqmusic_identity.h']},'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'limits':['Policy values are synthetic; service acceptance and actual Sony boot entropy remain unqualified.','No real account or hardware execution.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
