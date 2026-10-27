"""PC-only ARM/host ID3 writer fixture. Output must be below project work/."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
work=Path(sys.argv[1]).resolve()
assert work.is_relative_to((ROOT/'work').resolve()) and work.is_dir()
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
sources=['runtime/apps/qqmusic/qqmusic_id3.c','tools/fixtures/qqmusic_id3.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'id3-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),str(work/'cover.jpg')],capture_output=True,check=True,timeout=15)
(work/'generated.id3').write_bytes(run.stdout)
host=work/'id3-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*sources[:2],'-o',str(host)],cwd=ROOT,check=True)
host_run=subprocess.run([str(host),str(work/'cover.jpg')],capture_output=True,check=True,timeout=15)
assert host_run.stdout==run.stdout
(work/'build.json').write_text(json.dumps({'passed':True,'hardware_tested':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_id3.h','tools/build_qqmusic_id3_fixture.py']},'artifact_sha256':hashlib.sha256(app.read_bytes()).hexdigest()},indent=2)+'\n')
