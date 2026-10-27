"""Targeted font memory reduction and actual ARM renderer verification."""
from pathlib import Path
import hashlib,json,subprocess
from qqmusic_font_config import FONT,FONT_BYTES,FONT_SHA256
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-font-check';work.mkdir(exist_ok=True)
build=json.loads((ROOT/'work/qqmusic-device-full-5/build.json').read_text());codec=ROOT/'work/qqmusic-codec';lib=ROOT/'work/arm-signal-tests/lib'
objects=[]
for i,path in enumerate(build['sources']):
 if path in ('runtime/apps/qqmusic/qqmusic_ui.c','runtime/native/sha256.c'):objects.append(str(codec/(str(i)+'-'+Path(path).stem+'.o')))
assert len(objects)==2
common=['-std=gnu99','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-isystem','third_party/qqmusic-stb']
app=work/'font.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-O2','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','tools/fixtures/qqmusic_font.c',*objects,'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),str(codec/'libm.so.6'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
source=ROOT/'work/qqmusic-font/NotoSansCJKsc-Regular.otf'
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{codec}',str(app),str(source),str(FONT),str(work/'glyphs.ppm')],check=True)
host=work/'font.sanitized'
subprocess.run(['gcc-12',*common,'-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','tools/fixtures/qqmusic_font.c','runtime/apps/qqmusic/qqmusic_ui.c','runtime/native/sha256.c','-lm','-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host),str(source),str(FONT),str(work/'glyphs-host.ppm')],check=True)
assert (work/'glyphs.ppm').read_bytes()==(work/'glyphs-host.ppm').read_bytes()
report={'passed':True,'font_bytes':FONT_BYTES,'font_sha256':FONT_SHA256,'source_bytes':source.stat().st_size,'bytes_saved':source.stat().st_size-FONT_BYTES,'actual_arm_renderer':True,'asan_ubsan_passed':True,'checks':['new pinned font accepted; truncated/old font rejected','72 representative glyph/size raster and metrics match original','missing glyph outline retained','ARM and host glyph sheets identical'],'real_account_accessed':False,'physical_device_tested':False}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
