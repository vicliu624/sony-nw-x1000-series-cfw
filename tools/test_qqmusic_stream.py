"""Bounded streaming body tests against a synthetic transactional sink; no files downloaded."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-stream';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('session','protocol','cookie','http','response')]+['runtime/native/sha256.c','tools/fixtures/qqmusic_stream.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'stream-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)],cwd=ROOT,check=True,capture_output=True,timeout=30)
expected=hashlib.sha256(bytes(i%251 for i in range(3*1024*1024+17))).digest();assert run.stdout==expected
host=work/'stream-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
host_run=subprocess.run([str(host)],cwd=ROOT,check=True,capture_output=True,timeout=15);assert host_run.stdout==expected
report={'passed':True,'device_access':False,'objective_complete':False,
        'cases':['3MiB+17 streamed through <=4KiB sink calls','independent Python SHA256','defer finish, cancellation and truncation abort','write/finish error abort once','chunked framing, size cap, redirect rejection','cookieless response ignores Set-Cookie'],
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_response.h','runtime/apps/qqmusic/qqmusic_http.h','tools/test_qqmusic_stream.py']},
        'limits':['Synthetic sink, no native file transaction, no mount or device access.','No TLS/CDN streaming integration or audio validity check.','Sink finish means staged source complete, not playable/exported/imported.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
