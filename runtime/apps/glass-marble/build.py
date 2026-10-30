"""Offline ARM package and paired preview builder. Never deploys or opens devices."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from generate_espnow_full_profile import render
OUT=ROOT/'work/glass-marble';OUT.mkdir(parents=True,exist_ok=True)
APP=ROOT/'runtime/apps/glass-marble'
def run(args,**kw):return subprocess.run([str(a) for a in args],cwd=ROOT,check=True,**kw)
radio=OUT/('radio-'+str(time.time_ns()))
original=ROOT/'work/espnow-full-radio-review-3/stock'
run([sys.executable,ROOT/'tools/build_espnow_full_radio.py','--original',original/'sd8686.bin','--helper',original/'helper_sd.bin','--output',radio],stdout=subprocess.DEVNULL)
manifest=json.loads((radio/'manifest.json').read_text())
(OUT/'full_profile.h').write_text(render(radio))
header=['static const struct stock_input exchange_inputs[]={']
for name in ('sd8686.bin','helper_sd.bin'):
 data=(radio/'candidate'/name).read_bytes()
 header.append('{'+json.dumps('/contents/HOMEBREW/data/glass-marble/candidate/'+name)+','+str(len(data))+',{'+','.join(map(str,hashlib.sha256(data).digest()))+'}},')
(OUT/'exchange_inputs.h').write_text('\n'.join(header+['};'])+'\n')
run([sys.executable,ROOT/'runtime/platform/espnow/build_library.py'],stdout=subprocess.DEVNULL)
version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip()
library=ROOT/'work/espnow-native-library'/version/'sdk/lib/libxnow.a'
lib=ROOT/'work/arm-signal-tests/lib';stock=ROOT/'work/stock-resolver-probe'
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-unused-function','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-DHB_USE_POSIX_DEVICE_IO','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffunction-sections','-fdata-sections','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
 '-DXNOW_CANDIDATE_DIRECTORY="/contents/HOMEBREW/data/glass-marble/candidate"',
 '-I'+str(OUT),'-I'+str(ROOT/'runtime/platform/espnow'),'-I'+str(ROOT/'sdk/include'),'-I'+str(ROOT/'work/espnow-stock-reload-lab')]
shared=['runtime/apps/glass-marble/marble.c','runtime/apps/espnow-chat/chat_handoff.c','runtime/platform/espnow/xnow_managed_process.c','runtime/platform/espnow/xnow_handoff.c','runtime/native/app_process.c','runtime/native/linux_process_posix.c','runtime/store/start.c','runtime/store/start.S']
owner=['runtime/apps/glass-marble/owner.c','runtime/platform/espnow/xnow_owner_gate.c','runtime/platform/espnow/xnow_loader_job.c',*shared]
ui=['runtime/apps/glass-marble/app.c','runtime/apps/glass-marble/client.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c',*shared]
package=OUT/'HOMEBREW/apps/glass-marble';package.mkdir(parents=True,exist_ok=True)
dependencies=[library,stock/'libcnmgr.so.1','-Wl,--no-as-needed',stock/'libpthread.so.0',stock/'libm.so.6',lib/'libc.so.6',lib/'ld-linux.so.3','-lgcc']
run(['arm-linux-gnueabi-gcc',*flags,*owner,*dependencies,'-o',package/'radio-worker'])
worker=(package/'radio-worker').read_bytes()
(OUT/'worker_identity.h').write_text('#define GM_WORKER_BYTES '+str(len(worker))+'u\nstatic const unsigned char gm_worker_sha[32]={'+','.join(map(str,hashlib.sha256(worker).digest()))+'};\n')
run(['arm-linux-gnueabi-gcc',*flags,*ui,*dependencies,'-o',package/'app'])
data=(package/'app').read_bytes();sha=hashlib.sha256(data).hexdigest();app_version=(APP/'VERSION').read_text().strip()
(package/'app.ini').write_text(f'api=1\nid=glass-marble\nname=Glass Marble\nversion={app_version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={sha}\n')
(package/'launch.contract').write_text('XNOW-MANAGED-1\n'+sha+'\n')
(package/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.name}\n' for p in sorted(package.iterdir()) if p.is_file() and p.name!='files.sha256'))
base=['qemu-arm','-cpu','arm926',lib/'ld-linux.so.3','--library-path',str(lib)+':'+str(stock)]
for binary in ('app','radio-worker'):run([*base,package/binary,'--help'],stdout=subprocess.DEVNULL,timeout=15)
raw=subprocess.check_output([str(x) for x in [*base,package/'app','--render-preview']],cwd=ROOT,timeout=30)
assert len(raw)==240*432*2
from PIL import Image
def image(raw,w,h,path):
 rgb=bytearray()
 for i in range(0,len(raw),2):
  v=raw[i]|(raw[i+1]<<8);rgb.extend((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
 Image.frombytes('RGB',(w,h),bytes(rgb)).save(path)
image(raw,240,432,OUT/'x1060-preview.png')
sources=sorted(set(owner+ui))
report={'built':True,'version':app_version,'app_sha256':sha,'worker_sha256':hashlib.sha256(worker).hexdigest(),'radio_manifest':str(radio.relative_to(ROOT)/'manifest.json'),'radio_candidate_sha256':manifest['candidate_sha256'],'library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'hardware_tested':False,'device_written':False,'managed_launcher_required':True,'deployable':False,'pending':['physical S31 interoperability and latency','managed graphical app and APF/USB/sleep ownership'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
(OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
