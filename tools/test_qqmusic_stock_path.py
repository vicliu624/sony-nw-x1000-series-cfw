"""Pure candidate path policy from JP X1000 official MUSIC/eight-level rule."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-stock-path';work.mkdir(exist_ok=True)
core=['runtime/apps/qqmusic/qqmusic_stock_path.c','tools/fixtures/qqmusic_stock_path.c'];flags=['-std=c99','-Wall','-Wextra','-Werror']
host=work/'path-tests.sanitized';subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*core,'-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host)],check=True)
lib=ROOT/'work/arm-signal-tests/lib';arm=work/'path-tests.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],cwd=ROOT,check=True)
report={'passed':True,'device_tested':False,'scope':'pure_jp_x1000_music_destination_spelling_and_depth','checks':['MUSIC root and explicit subfolder','UTF8 artist/album/file path','file at eighth level accepted','ninth-level destination refused','lookalike roots and OMGAUDIO refused','dot traversal and malformed roots refused','relative escape and wrong component count refused','non-MP3 destination refused','small output buffer clears'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['runtime/apps/qqmusic/qqmusic_stock_path.h']},'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'limits':['No IO, mount verification, stock scan/refresh or physical playback.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
