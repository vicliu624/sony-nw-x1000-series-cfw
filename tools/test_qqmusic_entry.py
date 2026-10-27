"""Execute native entry lifecycle; collaborators injected, no hardware claims."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-entry';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
core=['runtime/apps/qqmusic/qqmusic_entry.c','tools/fixtures/qqmusic_entry.c']
flags=['-std=c99','-Wall','-Wextra','-Werror']
host=work/'entry-tests.sanitized'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=20)
lib=ROOT/'work/arm-signal-tests/lib';arm=work/'entry-tests.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],cwd=ROOT,check=True,timeout=20)
report={'passed':True,'scope':'entry_lifecycle_with_injected_collaborators','device_tested':False,'checks':['invalid config and preexisting stop','volume failure','asset failure','font rejection','runtime initialization failure','device open failure','loop initialization failure','normal loop exit','loop failure','display close failure','volume close failure','stop before device open','transport closes before display and font release'], 'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['runtime/apps/qqmusic/qqmusic_entry.h']},'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'limits':['Resource, renderer, transport and device collaborators are injected; tests verify entry orchestration only.','No real account, physical filesystem or hardware execution.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
