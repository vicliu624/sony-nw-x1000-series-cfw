"""ARM metadata precedence and ID3 encoding with host sanitizers, no source file writes."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-metadata';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_metadata.c','runtime/apps/qqmusic/qqmusic_id3.c','runtime/apps/qqmusic/qqmusic_image.c','runtime/apps/qqmusic/qqmusic_picture.c','runtime/native/sha256.c','tools/fixtures/qqmusic_metadata.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
stb=ROOT/'third_party/qqmusic-stb';math=ROOT/'work/qqmusic-codec/libm.so.6'
app=work/'metadata-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-isystem',str(stb),'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(math.parent),str(app)],cwd=ROOT,capture_output=True,check=True,timeout=15)
(work/'generated.id3').write_bytes(run.stdout)
host=work/'metadata-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-isystem',str(stb),'-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-lm','-o',str(host)],cwd=ROOT,check=True)
host_run=subprocess.run([str(host)],cwd=ROOT,capture_output=True,check=True,timeout=15);assert host_run.stdout==run.stdout
report={'passed':True,'synthetic_data':True,'objective_complete':False,'device_tested':False,
        'checks':['source first, matching IDs only fill missing','multiple artist, track total and precise date','genre/composer/unknown TXXX retained','sticky conflict/image/identity errors'],
        'tag_sha256':hashlib.sha256(run.stdout).hexdigest(),
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_metadata.h','runtime/apps/qqmusic/qqmusic_id3.h','tools/test_qqmusic_metadata.py']}}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
