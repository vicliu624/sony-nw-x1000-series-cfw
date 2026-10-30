"""Real nonblocking IPC pipes, actual full endpoint, synthetic RF; PC-only."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/espnow-owner-stream-tests';OUT.mkdir(parents=True,exist_ok=True)
sources=['tools/test_xnow_owner_stream.c']+['runtime/platform/espnow/'+n+'.c' for n in ['xnow_owner_stream','xnow_owner_commands','xnow_endpoint','xnow_peer','xnow_wire','xnow_full']]+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
wrap=['-Wl,--wrap=read','-Wl,--wrap=write'];host=OUT/'stream.host'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*wrap,*sources,'-o',str(host)],cwd=ROOT,check=True)
native=subprocess.run([str(host)],capture_output=True,text=True,timeout=30)
if native.returncode:print(native.stdout,native.stderr);native.check_returncode()
LIB=ROOT/'work/arm-signal-tests/lib';arm=OUT/'stream.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*wrap,*sources,'runtime/store/start.c','runtime/store/start.S',str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
target=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',str(LIB),str(arm)],capture_output=True,text=True,timeout=60)
if target.returncode:print(target.stdout,target.stderr);target.check_returncode()
dependencies=[*sources,'tools/test_xnow_owner_commands.c','tools/test_xnow_full.c','runtime/platform/espnow/xnow_owner_stream.h','runtime/platform/espnow/xnow_owner_commands.h','runtime/store/target_abi.h']
report={'passed':True,'host_asan_ubsan':native.stdout,'arm926_stock_libc':target.stdout,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependencies},'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'real_pipes':True,'short_io_injected':{'read_max':3,'write_max':5},'radio_transport_synthetic':True,'over_air_tested':False,'device_accessed':False,'installed':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
