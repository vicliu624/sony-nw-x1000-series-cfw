"""Build real-radio analysis owner profiles; never deploys or starts RF."""
import hashlib,json,os,subprocess,time,socket,struct,threading,sys
import argparse,re
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--window-seconds',type=int,choices=(60,180),default=60);parser.add_argument('--power-off-exit',action='store_true');parser.add_argument('--mode-view-required',action='store_true');parser.add_argument('--managed-session',action='store_true');parser.add_argument('--data-leaf',default='espnow-test',help='Single directory under /contents/HOMEBREW/data; existing keys/counters are never copied or reset');options=parser.parse_args()
if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',options.data_leaf):parser.error('Data leaf must be a single lowercase application directory')
if options.mode_view_required and not options.power_off_exit:parser.error('Mode-view owner requires power-off-exit profile')
if options.managed_session and (not options.mode_view_required or '--window-seconds' in sys.argv):parser.error('Managed session requires mode-view-required and no finite window argument')
out=ROOT/'work/remote-owner-build'/str(time.time_ns());out.mkdir(parents=True)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip()
sdk=ROOT/'work/espnow-native-library'/version/'sdk';receipt=json.loads((sdk/'build.json').read_text())
archive=sdk/'lib/libxnow.a';assert digest(archive)==receipt['archive_sha256']
for p,h in receipt['source_hashes'].items():assert digest(ROOT/p)==h,p
crypto=ROOT/'work/external-tls-probe/arm-build/libbearssl.a';assert digest(crypto)==receipt['bearssl_archive_sha256']
review=ROOT/'work/espnow-full-radio-review-3';manifest=json.loads((review/'manifest.json').read_text())
assert digest(review/'candidate/sd8686.bin')==manifest['candidate_sha256']=='d4b92b65fa502e2c8c94d241e4a293e28db7e98a3afdba0958d8b4f8aa1a5ed8'
assert digest(review/'radio.elf')==manifest['payload_elf_sha256']=='6918e3996088ebd99924e8c7039ad6ed26555aa3b0c411f2b9f765334c2218df'
prepared=ROOT/'work/autonomous-espnow-test';stock=ROOT/'work/espnow-stock-reload-lab'
assert digest(prepared/'full_profile.h')=='87dd58336a0e24bf73ca3d598afb73505878b5fcaec6ea43520d9a93fc567369'
assert digest(prepared/'exchange_inputs.h')=='ab9cdc6bfb0679576aacba088bb689f2fdfa4e02181286a803d7a8b0392552f4'
assert digest(stock/'stock_reload_inputs.h')=='c406c82fb40f8bcad5329e294813664558ebc694c86f2761e73d3a345f2c99e7'
data_directory='/contents/HOMEBREW/data/'+options.data_leaf
exchange_header=(prepared/'exchange_inputs.h').read_text()
assert exchange_header.count('/contents/HOMEBREW/data/espnow-test/candidate/')==2
(out/'exchange_inputs.h').write_text(exchange_header.replace('/contents/HOMEBREW/data/espnow-test/candidate/',data_directory+'/candidate/'))
libs=stock_libraries(include_rt=options.mode_view_required);cnmgr=ROOT/'work/stock-resolver-probe/libcnmgr.so.1'
assert digest(cnmgr)=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
sources=['runtime/apps/espnow-test/remote_owner.c','runtime/apps/espnow-test/runner.c','runtime/apps/espnow-test/detached.c']
sources+=['runtime/platform/espnow/'+n+'.c' for n in ('xnow_owner_gate','xnow_owner_runtime','xnow_owner_stream','xnow_owner_commands','xnow_owner_commands_control','xnow_handoff_owner','xnow_loader_job')]
sources+=['runtime/store/start.c','runtime/store/start.S']
if options.power_off_exit:sources+=['runtime/apps/wireless-remote/radio_stop.c','runtime/platform/wireless/radio_release.c','runtime/platform/espnow/xnow_power_off.c','runtime/platform/wireless/radio_modules.c']
if options.mode_view_required:sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/deadline.c']
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-D_DEFAULT_SOURCE=','-DHB_STORE_SONY_LIBC',
       '-DXNOW_REMOTE_WINDOW_MS='+str(options.window_seconds*1000)+'u',
       '-DXNOW_CANDIDATE_DIRECTORY="'+data_directory+'/candidate"','-DXNOW_USER_DATA_LEAF="'+options.data_leaf+'"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
       '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie',
       '-Wl,--hash-style=sysv,--build-id=none,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
       '-I'+str(out),'-I'+str(prepared),'-I'+str(ROOT/'runtime/platform/espnow'),'-I'+str(stock),
       '-I'+str(ROOT/'work/external-tls-probe/bearssl-0.6/inc')]
if options.power_off_exit:flags+=['-DXNOW_REMOTE_POWER_OFF']
if options.mode_view_required:flags+=['-DXNOW_REMOTE_MODE_VIEW','-DHB_STORE_LIBC_CLOCK']
if options.managed_session:flags+=['-DXNOW_REMOTE_MANAGED']
artifact=out/'remote-rf-owner.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(archive),str(crypto),str(cnmgr),
                '-Wl,--no-as-needed',str(libs['libpthread.so.0']),*([str(libs['librt.so.1'])] if options.mode_view_required else []),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in [*libs.values(),cnmgr])),str(artifact)]
env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
for args,expected in [(['--help'],0),([],64),(['--owner','3','3','4','00'*16,'020102030405','--charger-confirmed','--exclusive-radio-confirmed'],64)]:
 run=subprocess.run(base+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10);assert run.returncode==expected,run.stdout+run.stderr
startup_refusal=False;mode_admission_cases=[]
if not options.mode_view_required and '/dev/root / ext2 ro' not in Path('/proc/mounts').read_text():
 pairs=[os.pipe() for _ in range(3)];cookie=bytes(range(1,17))
 try:
  child_fds=[pairs[0][0],pairs[1][1],pairs[2][1]]
  run=subprocess.run(base+['--owner',*map(str,child_fds),cookie.hex(),'020102030405','--charger-confirmed','--exclusive-radio-confirmed'],
                     cwd=ROOT,env=env,pass_fds=child_fds,capture_output=True,text=True,timeout=10)
  assert run.returncode==69 and 'REMOTE_RF_OWNER_STARTING' not in run.stdout,run.stdout+run.stderr
  os.close(pairs[2][1]);pairs[2]=(pairs[2][0],-1)
  assert os.read(pairs[2][0],33)==b'XRFDONE1'+cookie+bytes([1,0,0,0,1,0,0,0])
  assert os.read(pairs[2][0],1)==b''
  startup_refusal=True
 finally:
  for pair in pairs:
   for fd in pair:
    if fd>=0:os.close(fd)
if options.mode_view_required:
 assert '/dev/root / ext2 ro' not in Path('/proc/mounts').read_text(),'PC-only refusal checks require a non-Sony root'
 for kind in ('matching','wrong-lease','revoked'):
  pairs=[os.pipe() for _ in range(3)];server,client=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM);server.settimeout(3)
  cookie=bytes(range(1,17));errors=[]
  def authority():
   try:
    request=server.recv(33);assert len(request)==32 and request[:4]==b'WMC1' and struct.unpack_from('<I',request,4)[0]==1 and struct.unpack_from('<I',request,16)[0]==0
    serial=struct.unpack_from('<Q',request,8)[0];reply=bytearray(80);reply[:4]=b'WMS1'
    struct.pack_into('<IQ',reply,4,1,serial)
    for offset,value in ((16,0),(20,3 if kind=='revoked' else 2),(24,2),(28,1 if kind=='revoked' else 2),(32,1),(36,0),(64,2),(68,1)):struct.pack_into('<I',reply,offset,value)
    struct.pack_into('<QQQ',reply,40,77,13 if kind=='wrong-lease' else 12,99)
    server.send(reply)
   except BaseException as error:errors.append(repr(error))
  thread=threading.Thread(target=authority);thread.start()
  try:
   fds=[pairs[0][0],pairs[1][1],pairs[2][1],client.fileno()]
   args=['--owner',*map(str,fds[:3]),cookie.hex(),'020102030405','--charger-confirmed','--exclusive-radio-confirmed','--mode-view',str(fds[3]),'77','12','99']
   run=subprocess.run(base+args,cwd=ROOT,env=env,pass_fds=fds,capture_output=True,text=True,timeout=10)
   thread.join(4);assert not thread.is_alive() and not errors,errors
   assert run.returncode==69 and 'REMOTE_RF_OWNER_STARTING' not in run.stdout,run.stdout+run.stderr
   admitted='REMOTE_RF_MODE_VIEW_AUTHORIZED' in run.stdout;assert admitted==(kind=='matching')
   os.close(pairs[2][1]);pairs[2]=(pairs[2][0],-1)
   assert os.read(pairs[2][0],33)==b'XRFDONE1'+cookie+bytes([1,0,0,0,1,0,0,0]) and os.read(pairs[2][0],1)==b''
   mode_admission_cases.append(dict(case=kind,admitted=admitted,refused_before_radio=True,returncode=run.returncode))
   if admitted:startup_refusal=True
  finally:
   server.close();client.close();thread.join(4)
   for pair in pairs:
    for fd in pair:
     if fd>=0:os.close(fd)
baseline=out/'espnow-test-baseline.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'runtime/apps/espnow-test/main.c',*sources[1:],str(archive),str(crypto),str(cnmgr),
                '-Wl,--no-as-needed',str(libs['libpthread.so.0']),*([str(libs['librt.so.1'])] if options.mode_view_required else []),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(baseline)],cwd=ROOT,check=True)
for args,expected in [(['--help'],0),([],64)]:
 run=subprocess.run(base[:-1]+[str(baseline)]+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10);assert run.returncode==expected,run.stdout+run.stderr
inputs=sources+['runtime/apps/espnow-test/main.c','runtime/apps/espnow-test/runner.h','runtime/platform/espnow/exchange_lab.c','runtime/platform/espnow/stock_reload_lab.c','runtime/platform/espnow/stock_wifi_session.c','tools/build_remote_owner.py']
if options.power_off_exit:inputs+=['runtime/platform/wireless/radio_release.h','runtime/platform/wireless/radio_modules.h']
if options.mode_view_required:inputs+=['runtime/apps/wireless-remote/owner_admission.h','runtime/platform/wireless/mode_client.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h','runtime/store/deadline.h']
inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/espnow').glob('*.h')]
inputs += [str(p.relative_to(ROOT)) for p in (prepared/'full_profile.h',prepared/'exchange_inputs.h',stock/'stock_reload_inputs.h')]
report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,sha256=digest(artifact),
            original_libc_arm_entry_checks=True,lab_only=True,window_seconds=None if options.managed_session else options.window_seconds,radio_started=False,device_accessed=False,
            finite_owner=not options.managed_session,lifetime_mode='supervised-session' if options.managed_session else 'finite-qualification',ready_for_native_settings=False,
            owner_mode_view_supported=options.mode_view_required,owner_mode_view_required=options.mode_view_required,mode_admission_cases=mode_admission_cases,
            continuous_mode_refresh_compiled=options.mode_view_required,mode_refresh_ms=200 if options.mode_view_required else 0,mode_stale_ms=1000 if options.mode_view_required else 0,
            power_off_exit_profile=options.power_off_exit,borrowed_stock_wifi_allowed=not options.power_off_exit,
            legacy_default_entry_checks=True,baseline_sha256=digest(baseline),
            non_sony_root_startup_refusal_receipt=startup_refusal,
            data_directory=data_directory,exchange_header=str((out/'exchange_inputs.h').relative_to(ROOT)),exchange_header_sha256=digest(out/'exchange_inputs.h'),
            candidate_sha256=manifest['candidate_sha256'],source_hashes={p:digest(ROOT/p) for p in inputs},
            linked_input_hashes={str(p.relative_to(ROOT)):digest(p) for p in (archive,crypto,cnmgr,*libs.values())},
            limits=['No hardware run or physical acceptance.','Legacy test storage/context remains unqualified for production.','Cooperative custom exclusion is not global Sony Wi-Fi/APF/USB/sleep arbitration.',
                    'Power-off-exit controller compiled; physical radio-off remains unqualified.' if options.power_off_exit else 'Default controller restores stock driver without proving radio-off.',
                    'Supervised lifetime compiled; persistent native Settings operation remains unqualified.' if options.managed_session else 'Finite test owner must not be presented as a persistent native Settings remote.'])
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
