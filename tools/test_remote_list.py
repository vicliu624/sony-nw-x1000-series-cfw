"""Remote list pagination, mapping and original touch decoding, offline."""
from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/remote-list-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/remote_list.c','runtime/store/canvas.c','runtime/native/frontend.c','tools/test_remote_list.c']
common=['-std=c99','-Wall','-Wextra','-Werror']
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
runtime=metadata['work'];bridge=['runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['running app excluded with original catalog index mapping','32 entries and final page bounds','next/previous/back and empty listing','drag ignored and second-page tap returns correct index','present failure and platform stop return without selection','invalid catalog rejected'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['runtime/native/app_list_art.h','runtime/native/app_icons_data.h','runtime/native/ui_font.h']},'limits':['Immutable parsed catalog and scripted touches, no native hardware.','No networking or metadata fetching in this unit test.','Known app titles/icons are compiled artwork; unknown IDs use a generic icon.']}
(ROOT/'sources/native-remote-list-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Remote list mapping/touch/paging passed on host and ARM/QEMU.')
