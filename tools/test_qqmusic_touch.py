"""Actual ARM UI/loop: press feedback precedes blocked/failed platform setup."""
from pathlib import Path
import argparse,hashlib,json,resource,subprocess
from qqmusic_font_config import FONT
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-touch';work.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);args=p.parse_args()
build=json.loads((ROOT/args.candidate/'build.json').read_text());codec=ROOT/'work/qqmusic-codec';lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe'
fixture=work/'touch.o';app=work/'touch.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(resolver),'-c','tools/fixtures/qqmusic_touch.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[str(codec/(str(i)+'-'+Path(name).stem+'.o')) for i,name in enumerate(build['sources']) if Path(name).suffix in ('.c','.S') and name not in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/native/syscalls.S')]
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',str(fixture),*objects,str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{codec}',str(app),str(FONT),str(work)],check=True,timeout=15)
report={'candidate_sha256':build['app_sha256'],'source_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('runtime/apps/qqmusic/qqmusic_ui.c','runtime/apps/qqmusic/qqmusic_loop.c','tools/fixtures/qqmusic_touch.c')},'passed':True,'actual_arm_ui_and_loop':True,'checks':['press changes button color before action','one tap on release only','visible tap receipt submitted before platform preparation','pending Wi-Fi produces distinct loading state','fast platform failure remains visible with retry button','held press submitted before pending preparation poll','settled unchanged screen submits zero extra frames across ten ticks'],'platform_network_simulated':True,'real_qr_or_login_requested':False}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
