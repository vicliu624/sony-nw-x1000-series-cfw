"""Actual Sony-loader negative test. Never maps or starts SpiderApp."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-host-refusal';work.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';stock=ROOT/'work/player-sqlite-ro';app=work/'refusal.arm'
sources=['runtime/platform/player/client.c','runtime/platform/player/stock_provider.c','runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_image.c','runtime/platform/player/stock_volume.c','runtime/platform/player/stock_gui.c','runtime/native/sha256.c','tools/fixtures/stock_host_refusal.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(stock/'libdl.so.2'),str(stock/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(stock)+':'+str(lib),str(app)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=15)
(work/'trace.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr[-3000:];assert not any(x in run.stderr for x in ('/dev/','/contents/','/db/','socket('))
report=dict(passed=True,actual_stock_loader=True,stock_image_not_loaded=True,device_accessed=False,stdout=run.stdout,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources})
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
