"""Original Sony BusyBox ash/unload function with mocked rmmod, no device."""
import hashlib,io,json,re,subprocess,tarfile,time
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
from elftools.elf.elffile import ELFFile
out=ROOT/'work/stock-wlan-unload'/str(time.time_ns());out.mkdir(parents=True)
root=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(root).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:
 script=archive.extractfile('./usr/local/bin/wlanapi.sh').read().decode('utf-8')
 function=re.search(r'w8_proc_unload\(\).*?\n}\n',script,re.S).group(0)
 member=next(m for m in archive if m.isfile() and m.name.endswith('/busybox'))
 busybox=out/'busybox';busybox.write_bytes(archive.extractfile(member).read())
 libs=stock_libraries()
 dynamic=ELFFile(io.BytesIO(busybox.read_bytes())).get_section_by_name('.dynamic')
 needed=[tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag=='DT_NEEDED'] if dynamic else []
 for name in needed:
  if name not in libs:
   entry=next(m for m in archive if m.name in ('./lib/'+name,'lib/'+name))
   path=out/name;path.write_bytes(archive.extractfile(entry).read());libs[name]=path
test=out/'test.sh'
test.write_text('''#!/bin/sh
PATH=/bin
DBG_ECHO=:
WTE_START=0
WIF=wlan0
w8_wlan_driver=sd8xxx
w8_sdio_driver=mp200_sdio
w8_wlan_pm_driver=wlan_pm_register
w8_wlan_pwr_driver=wlan_pwr_ctrl
chk_ifstate() { echo DOWN; }
rmmod() { echo "MOCK_RMMOD:$1"; [ "$1" != "$FAILED" ]; }
'''+function+'''
for FAILED in none sd8xxx mp200_sdio wlan_pm_register wlan_pwr_ctrl; do
 w8_proc_unload
 status=$?
 expected=0
 if [ "$FAILED" = sd8xxx ]; then expected=1; fi
 if [ "$status" != "$expected" ]; then echo UNLOAD_MISMATCH; exit 4; fi
 echo "UNLOAD_RESULT:$FAILED:$status"
done
echo STOCK_WLAN_UNLOAD_PASS
''')
init=out/'init.arm';init_source='tools/fixtures/player_worker_system_init.c'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none',init_source,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
markers=['STOCK_WLAN_UNLOAD_PASS','PLAYER_WORKER_CHILD_STATUS=0',*[f'UNLOAD_RESULT:{name}:{1 if name=="sd8xxx" else 0}' for name in ('none','sd8xxx','mp200_sdio','wlan_pm_register','wlan_pwr_ctrl')]]
guest=run_guest(out,init,{'test':test,'bin/sh':busybox,'bin/echo':busybox,'bin/[':busybox},libs,markers)
log=(out/'serial.log').read_text(errors='replace')
assert guest['passed'],log[-2500:]
assert log.count('MOCK_RMMOD:')==20
report=dict(passed=True,device_accessed=False,firmware_created=False,original_busybox_ash=True,
 busybox_sha256=hashlib.sha256(busybox.read_bytes()).hexdigest(),function_sha256=hashlib.sha256(function.encode()).hexdigest(),
 cases=[dict(failed=name,returned=1 if name=='sd8xxx' else 0) for name in ('none','sd8xxx','mp200_sdio','wlan_pm_register','wlan_pwr_ctrl')],
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/test_stock_wlan_unload.py',init_source,'runtime/store/start.c','runtime/store/start.S')},
 limits=['Original function and original shell execute in an isolated generic ARM guest.',
 'rmmod and interface-state commands are shell functions; no actual module unload/RF/kernel state mutation.',
 'Later rmmod errors can be hidden by the original let/status sequence, so script success alone is not full unload proof.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
