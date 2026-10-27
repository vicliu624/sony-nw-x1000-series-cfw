"""Offline application controller fixture, synthetic verified-login boundary."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-app';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export')
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in modules]+['runtime/store/https_url.c','runtime/native/sha256.c','tools/fixtures/qqmusic_app.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'app-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)],cwd=ROOT,check=True,timeout=15)
host=work/'app-tests.sanitized'
subprocess.run(['gcc-12','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host)],cwd=ROOT,check=True,timeout=15)
report={'passed':True,'real_account_tested':False,'device_tested':False,'objective_complete':False,
        'cases':['verified-login boundary to authenticated playlist request','default favorites to paginated songs and selection','selected media identity to authorization-ready and secret clear on back','pending and stale response tickets','back/logout/relogin/credential expiry'],
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_'+n+'.h' for n in modules]+['tools/test_qqmusic_app.py']},
        'limits':['Synthetic login-ready and authenticated-response boundaries, no network or real login in this fixture.',
                  'Controller only: no framebuffer/touch, download, conversion, persistence or stock refresh.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
