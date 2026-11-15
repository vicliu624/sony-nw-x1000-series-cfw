"""Pinned stb image/METADATA_BLOCK_PICTURE ARM fixture, no network or player IO."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];work=Path(sys.argv[1]).resolve()
assert work.is_dir() and work.is_relative_to((ROOT/'work').resolve())
stb=ROOT/'third_party/qqmusic-stb';manifest=json.loads((ROOT/'sources/qqmusic-image-sources.json').read_text())
for name,digest in manifest['files'].items():assert hashlib.sha256((stb/name).read_bytes()).hexdigest()==digest
lib=ROOT/'work/arm-signal-tests/lib';math=ROOT/'work/qqmusic-codec/libm.so.6'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
assert math.is_file(),'Build codec fixture to extract pinned stock libm first'
core=['runtime/apps/qqmusic/qqmusic_image.c','runtime/apps/qqmusic/qqmusic_picture.c','runtime/apps/qqmusic/qqmusic_metadata.c','runtime/apps/qqmusic/qqmusic_id3.c','runtime/native/sha256.c','tools/fixtures/qqmusic_artwork.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
app=work/'artwork-tests.arm'
flags=['-std=c99','-O2','-Wall','-Wextra','-Werror','-isystem',str(stb)]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
host=work/'artwork-tests.asan'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address','-fno-omit-frame-pointer',*core,'-lm','-o',str(host)],cwd=ROOT,check=True)
(work/'build.json').write_text(json.dumps({'built':True,'device_tested':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'stb_manifest_sha256':hashlib.sha256((ROOT/'sources/qqmusic-image-sources.json').read_bytes()).hexdigest()},indent=2)+'\n')
