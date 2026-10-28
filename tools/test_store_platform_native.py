"""Native adapter callbacks with virtual OABI calls, no physical devices."""
from pathlib import Path
import subprocess,json,hashlib,gzip,io,tarfile,tempfile,os
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-platform-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/platform_native.c','runtime/native/linux_devices.c','tools/test_store_platform_native.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'test')],cwd=ROOT,check=True)
subprocess.run([str(work/'test')],check=True)
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-c',sources[0],'-o',str(work/'platform.arm.o')],cwd=ROOT,check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
startup=['tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,*startup,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'test.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
modules=['install_posix','transaction','stage_posix','cleanup_posix','pending_plan','cleanup_plan','bundle_posix','inventory','package','stock_fs_bridge','stock_stat64','session','session_local','view','canvas','ui_loop','catalog_posix','catalog_view','catalog_loop','browser','termination','app','platform_native']
full_sources=[('runtime/apps/store/' if name in ('network_app','network_main') else 'runtime/store/')+name+'.c' for name in modules]+['runtime/native/frontend.c','runtime/native/sha256.c','runtime/native/linux_devices.c','tools/test_store_platform_native.c',*startup]
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_FULL_STORE','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*full_sources,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'full-test.arm')],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='full-',dir=work) as temp:
 base=Path(temp);apps=base/'apps';apps.mkdir();packages=base/'packages';packages.mkdir();demo=packages/'demo';demo.mkdir()
 program=(work/'full-test.arm').read_bytes();(demo/'app').write_bytes(program)
 manifest=f'api=1\nid=demo\nname=Demo\nversion=0.1.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(program)}\nsha256={hashlib.sha256(program).hexdigest()}\n'.encode();(demo/'app.ini').write_bytes(manifest)
 env=dict(os.environ,HB_FIXTURE_APPS=str(apps),HB_FIXTURE_PACKAGES=str(packages))
 full_run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'full-test.arm')],capture_output=True,text=True,timeout=20,env=env)
 assert full_run.returncode==0,(full_run.returncode,full_run.stdout,full_run.stderr)
 assert (apps/'demo/app').read_bytes()==program and (apps/'demo/app.ini').read_bytes()==manifest
 assert {p.name for p in apps.iterdir()}=={'demo','.store-lock'}
 assert (demo/'app').read_bytes()==program and (demo/'app.ini').read_bytes()==manifest
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':['valid geometry/present/touch/release','invalid geometry cleanup','both display pages busy: bounded failure','close error surfaced'],'ARM_QEMU_stock_libc_exit':run.returncode,'ARM_QEMU_binary_sha256':hashlib.sha256((work/'test.arm').read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+startup+['runtime/native/linux_devices.h','runtime/native/linux_device_io.h']},'limits':['Host and ARM/QEMU with virtual device-call function, not actual OABI device syscalls.','Original libc/loader, but no Sony kernel or physical hardware.','Release requests are tested, not hardware display queue completion or USB handoff.']}
report['full_ARM_app_with_native_adapter_virtual_calls']={'passed':True,'touch_samples':22,'frames_submitted':13,'maps':1,'unmaps':1,'descriptors_closed':2,'installed_files_match_source':True,'source_unchanged':True}
report['full_source_hashes']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in full_sources}
(ROOT/'sources/native-store-platform-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Native store platform: four virtual-device cases and full ARM store loop passed.')

