"""Exact private DSO cold routing under original Sony loader; no original GUI."""
import argparse,hashlib,io,json,subprocess,time,sys,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from review_managed_remote_profile import receipt,artifact
from player_arm_guest import stock_libraries,run_guest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host-review',required=True);parser.add_argument('--failed-firmware',help='Pinned physically failed first cold fix; assert its command7 defect, never a boot pass');parser.add_argument('--cold-exit-contract',action='store_true',help='Before owner binding, command3 must not poison future SDK native-exit state');parser.add_argument('--historical-library',help='Explicit pinned pre-fix library negative control, never a current-source pass');parser.add_argument('--native-repeat-contract',action='store_true',help='Resource-free unbound-radio native exit must remain delegated on repeat');args=parser.parse_args()
path,review=receipt(args.host_review)
assert review['native_rf_gate'] and review['native_sleep_analysis'] and review['managed_host']
library=path.parent/'libx1000-player-analysis.so';artifact(library,review['library_sha256'],review['library_bytes'])
if args.historical_library:
 from review_managed_remote_profile import private
 assert args.cold_exit_contract and not args.failed_firmware
 library=private(args.historical_library)
 assert hashlib.sha256(library.read_bytes()).hexdigest()=='4c2df66a1e701c8455752a92d432c297adefcefaf135501590a084cbff6fe1a4'
out=ROOT/'work/player-cold-dso'/str(time.time_ns());out.mkdir(parents=True)
baseline_sha=None
if args.failed_firmware:
 from review_managed_remote_profile import private
 sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
 firmware=private(args.failed_firmware);raw=firmware.read_bytes();baseline_sha=hashlib.sha256(raw).hexdigest()
 assert baseline_sha=='68e6b5d9659dd4bce756cdfa339cbf4af6db8f105b8276ed0de2648c4c4ebb0c'
 _,parts=unpack(raw,require_stock=False)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
  data=archive.extractfile('./usr/local/lib/libx1000-player.so').read()
 library=out/'failed-library.so';library.write_bytes(data)
elf=ELFFile(io.BytesIO(library.read_bytes()))
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
delta=symbols['xw_host_pid_dispatch']-symbols['getpid']
extra_flags=[]
if args.native_repeat_contract:assert args.cold_exit_contract and not args.historical_library
if args.cold_exit_contract:
 assert not baseline_sha
 extra_flags=['-DXW_TEST_NATIVE_EXIT_DELTA=('+str(symbols['native_exit_seen']-symbols['getpid'])+')',
              '-DXW_TEST_MANAGED_BIND_DELTA=('+str(symbols['xw_player_host_dispatch']-symbols['getpid'])+')',
              '-DXW_TEST_RESOURCES_IDLE_DELTA=('+str(symbols['xw_player_host_resources_idle']-symbols['getpid'])+')']
 if args.native_repeat_contract:extra_flags+=['-DXW_TEST_REPEAT_PREPARE_DELTA=('+str(symbols['xw_player_prepare_intercept']-symbols['getpid'])+')']
sources=['tools/fixtures/player_cold_dso.c','runtime/store/start.c','runtime/store/start.S']
libs=stock_libraries(include_rt=True,include_dl=True);binary=out/'init.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-DXW_TEST_DISPATCH_DELTA=('+str(delta)+')',*extra_flags,*(['-DXW_TEST_FAILED_BASELINE'] if baseline_sha else []),*sources,str(libs['libdl.so.2']),str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
libs['libx1000-player.so']=library
init_source='tools/fixtures/player_worker_system_init.c';init=out/'supervisor.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',init_source,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':binary},libs,['EXACT_DSO_COLD_PREPARE_ACTIVATE_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
report.update(historical_negative_control=bool(args.historical_library),cold_exit_contract_checked=args.cold_exit_contract,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),failed_firmware_sha256=baseline_sha,expected_command7_result='incorrectly HANDLED' if baseline_sha else 'delegate stock',hidden_dispatch_address_from_exact_elf=True,
 actual_dso_executed=True,stock_player_booted=False,device_accessed=False,
 limits=['Direct calls to the exact hidden dispatcher test unbound command6/7 and errno preservation; original stock caller/whole boot not executed.',
 'The separate instruction fixture covers patched ARM callsites. Generic kernel and no physical hardware qualification.'],
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,init_source,'tools/test_player_cold_dso.py','runtime/platform/player/host_prepare_bridge.h','runtime/platform/player/provider.h','runtime/platform/player/player.h']})
if args.cold_exit_contract:
 report['managed_bind_and_idle_checked']=True
 report['limits'].append('An explicit initialized xw_player fixture is supplied to the actual managed-service bind/idle query; original provider binding and live GUI event order are not executed.')
report['resource_free_repeat_contract_checked']=args.native_repeat_contract
report['original_linuxthreads_worker_pid_compared']=True
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert report['passed']
