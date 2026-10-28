"""Source executor ordering/ownership failures; all network/files/codec effects modeled."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-source-job';w.mkdir(exist_ok=True)
sources=['runtime/apps/qqmusic/qqmusic_preview_source_job.c','tools/fixtures/qqmusic_preview_source_job.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Iwork/bearssl-0.6/inc','-Iwork/stock-resolver-probe']
lib=ROOT/'work/arm-signal-tests/lib';host=w/'source.sanitized';arm=w/'source.arm'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*sources,'-Wl,--wrap=close','-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host)],check=True,timeout=10)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S','-Wl,--wrap=close',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],check=True,timeout=10)
report={'passed':True,'host_asan_ubsan':True,'stock_arm_libc':True,'cases':10,'physical_device_accessed':False,'account_accessed':False,'limits':['Network/download/volume/codec effects are modeled. Real source/codec/transport acceptance is separate.','Production receipt provider and UI/native-main binding remain pending.'],'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

