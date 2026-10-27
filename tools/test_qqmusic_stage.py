"""Real PC filesystem staged-source tests. Requires project FS distinct from Linux /."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-stage';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('session','protocol','cookie','http','response','stage','stage_volume')]+['runtime/native/sha256.c','tools/fixtures/qqmusic_stage.c']
sources=core+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'stage-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--wrap=write,--wrap=fsync','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='arm-',dir=work) as directory:
    run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),directory],cwd=ROOT,capture_output=True,text=True,timeout=30)
    (work/'fixture.trace').write_text(run.stderr)
    assert run.returncode==0,(run.returncode,run.stderr[-3000:])
    assert not list(Path(directory).iterdir())
    (work/'fixture.trace').write_text(run.stderr)
host=work/'stage-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wl,--wrap=write,--wrap=fsync',*core,'-o',str(host)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='host-',dir=work) as directory:
    subprocess.run([str(host),directory],cwd=ROOT,check=True,timeout=15)
    assert not list(Path(directory).iterdir())
report={'passed':True,'device_access':False,'objective_complete':False,
        'cases':['actual root filesystem rejection before create','pinned parent FD, exclusive create, streamed hash and synced source','collision preserves source','short write/EINTR retry, EIO/fsync/cancel cleanup','symlink replacement retained, foreign file untouched','directory alias changed to root does not redirect writes'],
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_stage.h','tools/test_qqmusic_stage.py']},
        'limits':['PC /mnt/c test workspace, not physical Sony FAT/USB qualification.','Caller must separately verify mount source and space before passing workspace FD.','No stock music publication, conversion, DB update or production app integration.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
