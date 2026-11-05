"""Real Sony libc/stat bridge resource readiness in isolated ARM Linux.

Fixture mutates only disposable RAM-guest files. No host/device root writes.
Pinned original GUI function-pointer ports compile but are not called here.
"""
import argparse,hashlib,json,subprocess,time
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from player_arm_guest import stock_libraries,run_guest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',required=True);args=parser.parse_args()
rp,review=receipt(args.review);header=private(review['guard_profile']);assert digest(header)==review['guard_profile_sha256']
assert len(review['resource_overlay'])==1
name,row=next(iter(review['resource_overlay'].items()));resource=private(row['artifact'])
assert digest(resource)==row['sha256'] and resource.stat().st_size==row['bytes']
out=ROOT/'work/remote-page-resource-ports'/str(time.time_ns());out.mkdir(parents=True)
libs=stock_libraries();binary=out/'resource.arm';init=out/'init.arm'
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none,-Ttext-segment=0x01000000,--dynamic-linker=/lib/ld-linux.so.3']
startup=['runtime/store/start.c','runtime/store/start.S']
sources=['runtime/platform/player/remote_page_ports.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/native/sha256.c','tools/fixtures/remote_page_resource_ports.c']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-I'+str(header.parent),*sources,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
init_source='tools/fixtures/player_worker_system_init.c'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,init_source,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':binary,name:resource,'resource-good.bin':resource},libs,['REMOTE_PAGE_RESOURCE_PORTS_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
report.update(original_libc_stat_bridge=True,resource_sha256=row['sha256'],guard_profile_sha256=digest(header),
 correct_resource_accepted=True,corrupt_missing_size_link_directory_rejected=True,fd_count_and_errno_preserved=True,
 native_gui_ports_executed=False,device_accessed=False,
 source_hashes={p:digest(ROOT/p) for p in sources+startup+[init_source,'tools/test_remote_page_resource_ports.py','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h']},
 limits=['Generic ARM kernel and disposable RAM root; test mutations are guest-only.',
         'Original libc/stat ABI, open/read/hash/close execute; native UI addresses only compile and are not called.',
         'No production resource installation, live view/controller or physical startup/RF acceptance.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
