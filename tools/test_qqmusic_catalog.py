"""Offline ARM and host-sanitized read-only QQ playlist/song response tests."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-catalog';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('session','protocol','json','credential','catalog','cgi')]+['tools/fixtures/qqmusic_catalog.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'catalog-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)],cwd=ROOT,check=True,timeout=15)
host=work/'catalog-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=15)
report={'passed':True,'real_account_tested':False,'device_tested':False,'objective_complete':False,
        'cases':['created/default favorites/collected playlists','UTF-8 song metadata and exact identifiers','pagination progress and total consistency','truncated responses and expired credential'],
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_catalog.h','tools/test_qqmusic_catalog.py']},
        'limits':['Synthetic fixed-version schema only.','No network integration, UI, resource authorization or downloads.','Bounded pages and JSON nodes: oversized responses rejected, never truncated.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
