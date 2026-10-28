"""Real staged source and durable receipt on mapped user-volume fixtures."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-receipt';w.mkdir(exist_ok=True)
sources=['runtime/apps/qqmusic/qqmusic_preview_receipt.c','runtime/apps/qqmusic/qqmusic_volume.c','runtime/apps/qqmusic/qqmusic_storage.c','runtime/apps/qqmusic/qqmusic_stage.c','runtime/apps/qqmusic/qqmusic_stage_volume.c','runtime/native/sha256.c','runtime/apps/qqmusic/qqmusic_protocol.c','tools/fixtures/qqmusic_preview_receipt.c']
flags=['-std=gnu99','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-format-truncation','-ffunction-sections','-fdata-sections','-Iwork/bearssl-0.6/inc','-Iwork/stock-resolver-probe']
wrap=['-Wl,--gc-sections,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=fsync']
lib=ROOT/'work/arm-signal-tests/lib';host=w/'receipt.sanitized';arm=w/'receipt.arm'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*sources,*wrap,'-o',str(host)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=w) as d:subprocess.run([str(host),d],check=True,timeout=15)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',*wrap,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=w) as d:subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm),d],check=True,timeout=20)
report={'passed':True,'host_asan_ubsan':True,'stock_arm_stat_bridge':True,'corruption_cases_per_backend':384,'truncation_cases_per_backend':384,'physical_device_accessed':False,'limits':['Mount paths map to a synthetic user-volume tree on the development computer.','No player, account or network access; physical durability is not qualified.'],'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

