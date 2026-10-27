"""Test normalized stock stat64 decoder on host and freestanding ARM926 QEMU."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-stat64-tests';work.mkdir(exist_ok=True)
source=['runtime/store/stock_stat64.c','tools/test_stock_stat64.c']
subprocess.run(['gcc','-DHB_STORE_HOST_FIXTURE','-std=c99','-O2','-Wall','-Wextra','-Werror',*source,'-o',str(work/'host-test')],cwd=ROOT,check=True)
subprocess.run([str(work/'host-test')],check=True,timeout=5)
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-Wall','-Wextra','-Werror','-nostdlib','-static','-Wl,-e,_start','-Wl,--build-id=none',*source,'runtime/native/support.c','tools/stock_stat64_start.S','-lgcc','-o',str(work/'arm-test')],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(work/'arm-test')],check=True,timeout=5)
report={'all_checks_passed':True,'physical_device_access':False,'source_sha256':hashlib.sha256((ROOT/source[0]).read_bytes()).hexdigest(),'ARM_test_sha256':hashlib.sha256((work/'arm-test').read_bytes()).hexdigest(),'checks':['normalized device/type/link/64-bit size/inode','reject112/104/95-byte buffers','reject sampled versions other than3','reject negative size without changing output','directory metadata','null input/output'],'host_passed':True,'freestanding_ARM926_QEMU_passed':True,'limits':['Pure data decoder only; ARM test uses OABI exit, no real stat or stock libc call.','Not yet connected to POSIX adapter; missing original-libc interfaces remain unresolved.','QEMU does not qualify original kernel/libc link, physical device or filesystem behavior.']}
(ROOT/'sources/native-stock-stat64-decoder.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock stat64 decoder: host and freestanding ARM926 QEMU passed.')
