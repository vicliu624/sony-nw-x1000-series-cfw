"""One targeted native fork/unmap regression; no network or real account."""
from pathlib import Path
import json,subprocess
from qqmusic_font_config import FONT
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-mapped-detach';work.mkdir(exist_ok=True)
build=json.loads((ROOT/'work/qqmusic-device-full-5/build.json').read_text());codec=ROOT/'work/qqmusic-codec';lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
fixture=work/'detach.o'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-c','tools/fixtures/qqmusic_mapped_detach.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[]
for i,name in enumerate(build['sources']):
 if Path(name).suffix not in ('.c','.S') or name in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/apps/qqmusic/qqmusic_import_binding.c','runtime/apps/qqmusic/qqmusic_devices.c','runtime/native/syscalls.S'):continue
 objects.append(str(codec/(str(i)+'-'+Path(name).stem+'.o')))
app=work/'detach.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--wrap=munmap','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',str(fixture),*objects,str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{codec}',str(app),str(FONT)],check=True,timeout=15)
report={'passed':True,'native_fork':True,'production_child_detach_function':True,'child_unmaps_readonly_font':True,'parent_mapping_and_pixels_unchanged':True,'child_account_erased':True,'device_close_simulated':True,'network_or_real_account_accessed':False}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
