"""Bounded generic ARM Linux startup of unchanged Sony sysmgrd; PC only."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,re,stat,struct,subprocess,tarfile,time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--normal-boot-fixture',action='store_true');parser.add_argument('--ram-state-fixture',action='store_true');parser.add_argument('--live-manager-fixture',action='store_true');parser.add_argument('--stock-home-fixture',action='store_true');parser.add_argument('--omf-ram-fixture',action='store_true');parser.add_argument('--stock-env-fallback-fixture',action='store_true');parser.add_argument('--empty-serial-fixture',action='store_true');parser.add_argument('--diagnostic-candidate');parser.add_argument('--launcher-failure',choices=['missing','invalid','crash']);parser.add_argument('--unresponsive-app-fixture',action='store_true');parser.add_argument('--player-bootstrap-fixture',action='store_true');parser.add_argument('--player-stock-composition');parser.add_argument('--home-switch-mode',type=int,choices=(0,1),default=0);parser.add_argument('--home-quit-delay-ms',type=int,default=0);parser.add_argument('--home-sdk-drain-fixture',action='store_true');parser.add_argument('--resident-fixture',action='store_true');parser.add_argument('--missing-resident-fixture',action='store_true');parser.add_argument('--resident-exit-fixture',action='store_true');parser.add_argument('--resident-sdk-fixture',action='store_true');parser.add_argument('--resident-restart-fixture',action='store_true');parser.add_argument('--resident-exit-code',type=int,choices=(0,23),default=0);parser.add_argument('--interdsp-open-probe',action='store_true',help='Guest-only handle; reject every DSP ioctl, never model DSP success');options=parser.parse_args()
if options.resident_fixture or options.missing_resident_fixture or options.resident_exit_fixture or options.resident_sdk_fixture:assert options.live_manager_fixture
assert sum((options.resident_fixture,options.missing_resident_fixture,options.resident_exit_fixture,options.resident_sdk_fixture))<=1
if options.resident_restart_fixture:assert options.resident_exit_fixture and not options.resident_exit_code
if options.resident_exit_code:assert options.resident_exit_fixture
if options.home_sdk_drain_fixture:assert options.home_switch_mode==1 and not options.home_quit_delay_ms
if options.home_switch_mode:assert options.live_manager_fixture and not options.diagnostic_candidate and not options.player_bootstrap_fixture
assert 0<=options.home_quit_delay_ms<=2000
if options.home_quit_delay_ms:assert options.home_switch_mode==1
if options.player_stock_composition:assert options.stock_home_fixture and not options.player_bootstrap_fixture
if options.player_bootstrap_fixture:assert options.live_manager_fixture and not options.stock_home_fixture and not options.diagnostic_candidate
if options.diagnostic_candidate:assert options.live_manager_fixture
if options.launcher_failure:assert options.diagnostic_candidate
if options.unresponsive_app_fixture:assert options.diagnostic_candidate and not options.launcher_failure
if options.live_manager_fixture:assert options.normal_boot_fixture and options.ram_state_fixture
if options.stock_home_fixture:assert options.normal_boot_fixture and options.ram_state_fixture and not options.live_manager_fixture
if options.omf_ram_fixture:assert options.stock_home_fixture
if options.interdsp_open_probe:assert options.stock_home_fixture
if options.stock_env_fallback_fixture:assert options.stock_home_fixture
if options.empty_serial_fixture:assert options.stock_home_fixture and options.normal_boot_fixture
work=(ROOT/options.output).resolve();assert work.is_relative_to(ROOT/'work');work.mkdir(exist_ok=False)
stock=ROOT/'work/stock-manager-runtime-probe/root';lib=stock/'lib'
manager=stock/'usr/local/bin/sysmgrd'
assert hashlib.sha256(manager.read_bytes()).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
kernel=ROOT/'work/arm-system-probe/vmlinuz-2.6.32-5-versatile'
assert hashlib.md5(kernel.read_bytes()).hexdigest()=='8782441dee9e950c538140ec54f52e87'
block_inputs=[]
if options.ram_state_fixture:
 block=ROOT/'work/arm-block-kernel';manifest=json.loads((block/'inputs.json').read_text())
 for row in manifest['files']:assert hashlib.sha256((block/row['name']).read_bytes()).hexdigest()==row['sha256']
 kernel=block/'vmlinuz-2.6.32-5-versatile';block_inputs += [block/'inputs.json']
 state=work/'empty-var.ext2'
 with state.open('xb') as output:output.truncate(4*1024*1024)
 subprocess.run(['mke2fs','-q','-F','-t','ext2','-b','4096','-O','none',str(state)],check=True)
 block_inputs += [kernel,state]+[block/name for name in ('brd.ko','mbcache.ko','ext2.ko')]
source=ROOT/'tools/fixtures/stock_manager_init.c';device_source=ROOT/'tools/fixtures/manager_device_preload.c'
flags=['-march=armv5te','-marm','-mfloat-abi=soft','-nostdlib','-Wl,--hash-style=sysv']
if options.player_bootstrap_fixture or options.player_stock_composition:flags.insert(0,'-DHB_PLAYER_BOOTSTRAP_FIXTURE')
if options.ram_state_fixture:flags.insert(0,'-DHB_RAM_STATE')
if options.live_manager_fixture:flags.insert(0,'-DHB_LIVE_MANAGER')
if options.home_switch_mode:flags.insert(0,'-DHB_HOME_QUIT_MODE')
if options.home_quit_delay_ms:flags.insert(0,'-DHB_HOME_QUIT_DELAY_MS='+str(options.home_quit_delay_ms))
if options.home_sdk_drain_fixture:flags.insert(0,'-DHB_MANAGER_DRAIN_FIXTURE')
if options.resident_restart_fixture:flags.insert(0,'-DHB_RESIDENT_RESTART_FIXTURE')
if options.resident_fixture:flags.insert(0,'-DHB_RESIDENT_FIXTURE')
if options.omf_ram_fixture:flags.insert(0,'-DHB_OMF_PARAM_RAM')
if options.interdsp_open_probe:flags.insert(0,'-DHB_INTERDSP_OPEN_PROBE')
init=work/'init.arm';devices=work/'manager-devices.so'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-no-pie','-fno-pie',str(source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(init)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-shared','-fPIC',str(device_source),str(lib/'libc.so.6'),str(lib/'libdl.so.2'),'-o',str(devices)],check=True)
archive=bytearray();inode=1
def add(name,data=b'',mode=stat.S_IFREG|0o755,major=0,minor=0):
 global inode
 encoded=name.encode()+b'\0';fields=[inode,mode,0,0,1,0,len(data),0,0,major,minor,len(encoded),0];inode+=1
 archive.extend(b'070701'+b''.join(('%08x'%n).encode() for n in fields)+encoded);archive.extend(b'\0'*(-len(archive)%4));archive.extend(data);archive.extend(b'\0'*(-len(archive)%4))
stock_packed=None
if options.stock_home_fixture:
 stock_packed=ROOT/'work/upg-jp/verified-3.bin'
 assert hashlib.sha256(stock_packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
 overrides={'init','etc/AppList.conf','usr/local/bin/sysmgrd','lib/ld-linux.so.3','lib/libc.so.6','lib/libpthread.so.0','lib/libresolv.so.2','lib/libdl.so.2'}
 if options.player_stock_composition:overrides.add('usr/local/bin/SpiderApp')
 with tarfile.open(stock_packed,'r:gz') as tar:
  for member in tar:
   name=member.name.removeprefix('./');assert not name.startswith('/') and '..' not in name.split('/')
   if name in overrides or name=='.':continue
   if member.isdir():add(name,mode=stat.S_IFDIR|member.mode)
   elif member.isfile():add(name,tar.extractfile(member).read(),stat.S_IFREG|member.mode)
   elif member.issym():add(name,member.linkname.encode(),stat.S_IFLNK|member.mode)
   elif member.islnk():add(name,tar.extractfile(member).read(),stat.S_IFREG|member.mode)
for name in ('dev','dev/mtdblock','proc','sys','tmp','var','db','ep0','run','contents','etc','lib','usr','usr/local','usr/local/bin'):add(name,mode=stat.S_IFDIR|0o755)
add('dev/console',mode=stat.S_IFCHR|0o600,major=5,minor=1);add('dev/null',mode=stat.S_IFCHR|0o666,major=1,minor=3)
if options.normal_boot_fixture:
 add('dev/icx1087_nvp',mode=stat.S_IFDIR|0o755)
 # Explicit guest-only nonmatching tags: not measured or default device data.
 add('dev/icx1087_nvp/22',b'TEST',stat.S_IFREG|0o600)
 add('dev/icx1087_nvp/18',b'TEST',stat.S_IFREG|0o600)
if options.stock_env_fallback_fixture:
 # b97d4..b9820 supplies 0x05020004 on a short read; not measured JP NVP.
 add('dev/icx1087_nvp/16',struct.pack('<I',0x05020004),stat.S_IFREG|0o600)
if options.empty_serial_fixture:
 # Env_getSerialNo b9868 reads 8 bytes; short reads select an empty string.
 # No fabricated serial or real device identifier is introduced.
 add('dev/icx1087_nvp/4',b'',stat.S_IFREG|0o600)
if options.ram_state_fixture:
 for name in ('brd.ko','mbcache.ko','ext2.ko'):add(name,(block/name).read_bytes())
 add('fixture-var.ext2',state.read_bytes(),stat.S_IFREG|0o600)
add('init',init.read_bytes());add('usr/local/bin/sysmgrd',manager.read_bytes());add('lib/manager-devices.so',devices.read_bytes())
additional=[]
configuration=stock/'etc/AppList.conf'
if options.stock_home_fixture:
 configuration=work/'AppList.conf';configuration.write_text('0x00000001 * SpiderApp\n0x00000002 * Responder\n0x00020001 app netfront\n')
if options.player_stock_composition:
 composition=(ROOT/options.player_stock_composition).resolve();assert composition.is_relative_to(ROOT/'work')
 payload=composition/'SpiderApp.home-language-player-met.analysis-only.elf'
 composition_report=json.loads((composition/'report.json').read_text());assert composition_report['passed'] and hashlib.sha256(payload.read_bytes()).hexdigest()==composition_report['combined_sha256']
 from build_player_host import build as build_player_host
 player_library,_,player_report=build_player_host();wrapper=work/'SpiderApp.bootstrap.arm';bootstrap_source=ROOT/'runtime/platform/player/bootstrap.c'
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-Wl,-Ttext-segment=0x01000000','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"',str(bootstrap_source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(wrapper)],cwd=ROOT,check=True)
 for directory in ('usr/local/lib','usr/local/lib/x1000-player'):add(directory,mode=stat.S_IFDIR|0o755)
 add('usr/local/bin/SpiderApp',wrapper.read_bytes());add('usr/local/lib/x1000-player/SpiderApp',payload.read_bytes());add('lib/libx1000-player.so',player_library.read_bytes())
 additional += [bootstrap_source,wrapper,payload,composition/'report.json',player_library,ROOT/'work/player-host/build.json']
if options.live_manager_fixture:
 configuration=work/'AppList.conf'
 configuration.write_text('0x00000001 * /usr/local/bin/test-home\n0x00000002 * /usr/local/bin/test-responder\n0x00030001 * /contents/HOMEBREW/launcher/app --native\n')
 if options.missing_resident_fixture:
  configuration.write_text(configuration.read_text()+'0x00010010 * /contents/HOMEBREW/apps/missing-resident/app\n')
 if options.resident_fixture or options.resident_exit_fixture or options.resident_sdk_fixture:
  configuration.write_text(configuration.read_text()+'0x00010010 * /usr/local/bin/test-resident\n')
  resident_source=ROOT/'tools/fixtures/manager_resident_client.c';resident=work/'resident.arm'
  sdk_sources=[]
  if options.resident_sdk_fixture:
   sdk_sources=['runtime/platform/player/'+n+'.c' for n in ('client','managed','managed_rpc','rpc_wire','managed_channel','managed_control','managed_codec','managed_remote','managed_client','managed_clock','managed_host','session_offer','service_drain','deferred_prepare')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['runtime/store/deadline.c']
   consumer=work/'sdk-managed-client.arm';consumer_source=ROOT/'sdk/tests/player_managed_channel.c'
   subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-std=c99','-Os','-DHB_STORE_LIBC_CLOCK','-I'+str(ROOT/'sdk/include'),'-fno-stack-protector','-no-pie','-fno-pie',str(consumer_source),*sdk_sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libpthread.so.0'),str(lib/'librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(consumer)],cwd=ROOT,check=True)
   add('usr/local/bin/sdk-managed-client',consumer.read_bytes());additional += [consumer,consumer_source,ROOT/'tools/fixtures/managed_host_external.c']+[ROOT/p for p in sdk_sources]
   additional += [p for folder in ('runtime/platform/player','runtime/platform/services','sdk/include/x1000/services') for p in (ROOT/folder).glob('*.h')]
  subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-std=c99','-O1','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie',*(['-DHB_RESIDENT_EXIT_FIXTURE','-DHB_RESIDENT_EXIT_CODE='+str(options.resident_exit_code)] if options.resident_exit_fixture else []),*(['-DHB_RESIDENT_SDK_FIXTURE','-DHB_STORE_LIBC_CLOCK'] if options.resident_sdk_fixture else []),str(resident_source),*sdk_sources,'runtime/store/start.c','runtime/store/start.S',*([str(lib/'libpthread.so.0'),str(lib/'librt.so.1')] if options.resident_sdk_fixture else []),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(resident)],cwd=ROOT,check=True)
  add('usr/local/bin/test-resident',resident.read_bytes());additional += [resident_source,resident]
 client_source=ROOT/'tools/fixtures/manager_home_client.c';client=work/'home-client.arm'
 drain_sources=[]
 if options.home_sdk_drain_fixture:
  drain_sources=['runtime/platform/player/'+n+'.c' for n in ('client','managed','managed_rpc','managed_channel','managed_control','rpc_wire','player_broker','metadata_async','local_identity','service_drain','drain_completion','deferred_prepare','managed_host','session_offer')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]+['tools/fixtures/player_service_drain_threads.c']
  additional += [ROOT/p for p in drain_sources]+[ROOT/'tools/fixtures/player_broker.c']
  additional += [p for folder in ('runtime/platform/player','runtime/platform/services') for p in (ROOT/folder).glob('*.h')]
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,*(['-DHB_UNRESPONSIVE_APP_FIXTURE'] if options.unresponsive_app_fixture else []),'-std=c99','-O1','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie',str(client_source),*drain_sources,'runtime/store/start.c','runtime/store/start.S',*([str(lib/'libdl.so.2')] if options.player_bootstrap_fixture else []),*([str(lib/'libpthread.so.0')] if options.home_sdk_drain_fixture else []),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(client)],cwd=ROOT,check=True)
 if options.player_bootstrap_fixture:
  from build_player_host import build as build_player_host
  player_library,_,player_report=build_player_host();wrapper=work/'SpiderApp.bootstrap.arm';bootstrap_source=ROOT/'runtime/platform/player/bootstrap.c'
  subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-Wl,-Ttext-segment=0x01000000','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"',str(bootstrap_source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(wrapper)],cwd=ROOT,check=True)
  configuration.write_text('0x00000001 * SpiderApp\n0x00000002 * Responder\n0x00030001 * /contents/HOMEBREW/launcher/app --native\n')
  for directory in ('usr/local/lib','usr/local/lib/x1000-player'):add(directory,mode=stat.S_IFDIR|0o755)
  add('usr/local/bin/SpiderApp',wrapper.read_bytes());add('usr/local/lib/x1000-player/SpiderApp',client.read_bytes());add('usr/local/bin/Responder',client.read_bytes());add('lib/libx1000-player.so',player_library.read_bytes())
  additional += [bootstrap_source,wrapper,player_library,ROOT/'work/player-host/build.json']
 else:
  add('usr/local/bin/test-home',client.read_bytes());add('usr/local/bin/test-responder',client.read_bytes())
 proxy=stock/'usr/local/bin/appproxy';assert hashlib.sha256(proxy.read_bytes()).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479';add('usr/local/bin/appproxy',proxy.read_bytes())
 device_source2=ROOT/'tools/fixtures/system_device_preload.c';devices2=work/'system-devices.so'
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,*(['-DHB_DIAGNOSTIC_APP'] if options.diagnostic_candidate else []),'-shared','-fPIC',str(device_source2),str(lib/'libc.so.6'),str(lib/'libdl.so.2'),'-o',str(devices2)],check=True)
 add('lib/system-devices.so',devices2.read_bytes())
 if options.diagnostic_candidate:
  composition=(ROOT/options.diagnostic_candidate).resolve();assert composition.is_relative_to(ROOT/'dist')
  candidate_profile=json.loads((composition/'review/verification.json').read_text())['profile']
  verifier_name={'compact-resource-feedback-local-review':'verify_compact_feedback_diagnostic.py',
                 'external-stop-fix-local-review':'verify_external_stop_review.py'}.get(candidate_profile,'verify_diagnostic_candidate.py')
  candidate_verifier=ROOT/'tools'/verifier_name
  subprocess.run([str(ROOT/'.venv/bin/python'),str(candidate_verifier),options.diagnostic_candidate],check=True,cwd=ROOT)
  fault_app=None
  if options.unresponsive_app_fixture:
   fault_source=ROOT/'tools/fixtures/unresponsive_system_app.c';fault_app=work/'unresponsive-app.arm'
   subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-no-pie','-fno-pie',str(fault_source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(fault_app)],cwd=ROOT,check=True)
   additional += [fault_source,fault_app]
  tree=composition/'external'
  for directory in sorted([tree,*[p for p in tree.rglob('*') if p.is_dir()]],key=lambda p:len(p.parts)):add('contents'+str(directory.relative_to(tree)).removeprefix('.') if directory==tree else 'contents/'+str(directory.relative_to(tree)),mode=stat.S_IFDIR|0o755)
  for path in sorted(tree.rglob('*')):
   if not path.is_file():continue
   additional.append(path);data=path.read_bytes()
   if options.unresponsive_app_fixture and path==tree/'HOMEBREW/apps/diagnostics/app':data=fault_app.read_bytes()
   if options.unresponsive_app_fixture and path==tree/'HOMEBREW/apps/diagnostics/app.ini':
    text=data.decode();payload=fault_app.read_bytes()
    text=re.sub(r'^bytes=.*$', 'bytes='+str(len(payload)),text,flags=re.M)
    text=re.sub(r'^sha256=.*$', 'sha256='+hashlib.sha256(payload).hexdigest(),text,flags=re.M);data=text.encode()

   if path==tree/'HOMEBREW/launcher/app' and options.launcher_failure:
    if options.launcher_failure=='missing':continue
    if options.launcher_failure=='invalid':data=b'\x7fELF\x01INVALID-GUEST-FIXTURE\n'
    else:
     crash_source=ROOT/'tools/fixtures/launcher_crash.c';crash=work/'launcher-crash.arm'
     subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-no-pie','-fno-pie',str(crash_source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(crash)],cwd=ROOT,check=True)
     data=crash.read_bytes();additional += [crash_source,crash]
   add('contents/'+str(path.relative_to(tree)),data)
  additional += [composition/'SHA256SUMS',composition/'review/verification.json',composition/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG',candidate_verifier,ROOT/'runtime/native/font.inc',ROOT/'runtime/native/frontend.h']
 else:
  composition=ROOT/'work/store-setup-workflow-fixture';manifest2=json.loads((composition/'manifest.json').read_text())
  for name in ('contents/HOMEBREW','contents/HOMEBREW/launcher','contents/HOMEBREW/apps','contents/HOMEBREW/apps/graphics-demo'):add(name,mode=stat.S_IFDIR|0o755)
  for relative in ('external/HOMEBREW/launcher/app','external/HOMEBREW/apps/graphics-demo/app','external/HOMEBREW/apps/graphics-demo/app.ini'):
   path=composition/relative;row=next(row for row in manifest2['files'] if row['path']==relative);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'];add(relative.replace('external/','contents/',1),path.read_bytes());additional.append(path)
  additional.append(composition/'manifest.json')
 for name in ('passwd','group'):add('etc/'+name,(stock/'etc'/name).read_bytes())
 additional += [client_source,client,proxy,device_source2,devices2,stock/'etc/passwd',stock/'etc/group']
add('etc/AppList.conf',configuration.read_bytes())
names=('ld-linux.so.3','libc.so.6','libpthread.so.0','libresolv.so.2','libdl.so.2')
if options.player_bootstrap_fixture or options.player_stock_composition or options.resident_sdk_fixture:names+=('librt.so.1',)
for name in names:add('lib/'+name,(lib/name).read_bytes())
add('TRAILER!!!',mode=0);initrd=work/'manager-initramfs.cpio.gz';initrd.write_bytes(gzip.compress(bytes(archive),mtime=0))
extract=ROOT/'work/qemu-system-tool/extracted';qemu=extract/'usr/bin/qemu-system-arm'
command=[str(qemu),'-M','versatilepb','-cpu','arm926','-m','256M' if options.stock_home_fixture else '128M','-display','none','-monitor','none','-serial','stdio','-nic','none','-kernel',str(kernel),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init panic=0','-no-reboot']
env=dict(os.environ);env['LD_LIBRARY_PATH']=str(extract/'usr/lib/x86_64-linux-gnu');env['QEMU_AUDIO_DRV']='none'
observed=False;timed_out=False
with (work/'serial.log').open('wb') as serial,(work/'qemu.log').open('wb') as errors:
 process=subprocess.Popen(command,stdout=serial,stderr=errors,env=env);deadline=time.monotonic()+20
 while process.poll() is None and time.monotonic()<deadline:
  if b'GUEST_MANAGER_PROBE_COMPLETE' in (work/'serial.log').read_bytes():observed=True;process.terminate();break
  time.sleep(0.05)
 if process.poll() is None and not observed:timed_out=True;process.kill()
 code=process.wait(timeout=5)
tracked=[Path(__file__),source,device_source,init,devices,manager,configuration,kernel,initrd,qemu,work/'serial.log',work/'qemu.log',ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S',ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz',ROOT/'work/manager-pm-source/drivers_char_mp200_pm_ext.c',ROOT/'work/manager-pm-source/include_asm-arm_arch-mp200_mp200_pm_ext.h']+[lib/n for n in names]
tracked += [ROOT/'work/manager-power-source/icx1087_power.h',lib.parent/'lib/modules/icx1087_power.ko']
tracked += [ROOT/'work/manager-power-source/icx1087_cradle.h',ROOT/'work/manager-power-source/icx1087_cradle.c']
tracked += block_inputs
tracked += additional
if stock_packed:tracked.append(stock_packed)
if options.omf_ram_fixture:tracked += [ROOT/'work/manager-power-source/mp201_mem.h',ROOT/'work/manager-power-source/memory.h']
report={'scope':'Stock manager startup with explicit unplugged USB, idle PM and steady battery query models; original AppList references absent applications; no Sony hardware qualification','normal_boot_nvp_fixture':options.normal_boot_fixture,'nvp_fixture_bytes':'TEST' if options.normal_boot_fixture else None,'exit':code,'observation_complete':observed,'timed_out':timed_out,'command':command,'physical_device_access':False,'internal_address_hooks':False,'device_io_interposed':True,'unknown_device_ioctls':'EOPNOTSUPP','source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
report['ram_state_fixture']=options.ram_state_fixture
report['ram_state_partitions']=[3,4,5] if options.ram_state_fixture else []
report['mount_interposed']=False
report['live_manager_fixture']=options.live_manager_fixture
report['stock_home_fixture']=options.stock_home_fixture
report['omf_parameter_ram_model']=options.omf_ram_fixture
report['interdsp_open_probe']=options.interdsp_open_probe
report['dsp_execution_or_success_modeled']=False
report['environment_fallback_fixture']='0x05020004 (stock short-read fallback, not measured device NVP)' if options.stock_env_fallback_fixture else None
report['serial_fixture']='empty file, original short-read fallback' if options.empty_serial_fixture else None
if options.stock_home_fixture:report['scope']='Unmodified SpiderApp with stock rootfs files, minimal test AppList, simulated manager devices and RAM state volumes; startup observation only, not Sony GUI qualification'
if options.stock_home_fixture:
 startup_output=(work/'serial.log').read_text(errors='replace')
 report['startup_panics']=re.findall(r'PANIC at ([^\r\n!]+)',startup_output)
 report['full_gui_qualified']=False
 report['hardware_mem_open_observed']='MANAGER_DEVICE OPEN /dev/mem' in startup_output
 report['startup_success_claimed']=False
if options.player_stock_composition:
 report.update(scope='Actual composed SpiderApp through optional exec wrapper and player DSO with original manager/rootfs; virtual devices and RAM, bounded startup observation only',player_stock_composition=options.player_stock_composition,player_library_sha256=player_report['library_sha256'],ready_to_flash=False,full_gui_qualified=False,process_calls_interposed=True,process_lifecycle_calls_interposed=False)
report['test_home_client_not_sony_gui']=options.live_manager_fixture
report['diagnostic_candidate']=options.diagnostic_candidate
report['guest_launcher_failure_fixture']=options.launcher_failure
report['live_return_observed']=b'LIVE_MANAGER_RETURN_CONFIRMED' in (work/'serial.log').read_bytes()
if options.live_manager_fixture:
 output=(work/'serial.log').read_text(errors='replace')
 ordered=['HOME_CLIENT_STARTED','HOME_REPLY 0 0 0','HOME_REPLY 1 1 0','HOME_REPLY 2 36 0','HOME_REPLY 3 6 0','HOME_DEACTIVATED','SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE GRAPHICS OPEN','SYSTEM_DEVICE GRAPHICS RELEASED','SYSTEM_DEVICE LAUNCHER REOPEN','LIVE_MANAGER_RETURN_CONFIRMED','GUEST_MANAGER_STOP_AFTER_COMPLETION']
 if options.home_switch_mode:ordered=[s.replace('HOME_DEACTIVATED','HOME_QUIT_REQUESTED') for s in ordered];ordered.insert(ordered.index('LIVE_MANAGER_RETURN_CONFIRMED'),'HOME_RESTART_CONFIRMED')
 if options.resident_restart_fixture:
  ordered=[s.replace('HOME_REPLY 2 36 0','HOME_REPLY 3 36 0').replace('HOME_REPLY 3 6 0','HOME_REPLY 4 6 0') for s in ordered]
  position=ordered.index('HOME_REPLY 3 36 0')
  ordered[position:position]=['HOME_REPLY 2 2 0','HOME_RESIDENT_START_ACCEPTED']
 if options.home_quit_delay_ms:
  position=ordered.index('HOME_QUIT_REQUESTED')+1
  ordered[position:position]=['HOME_QUIT_DELAY_BEGIN '+str(options.home_quit_delay_ms),'HOME_QUIT_DELAY_FINISHED']
 if options.home_sdk_drain_fixture:
  position=ordered.index('HOME_QUIT_REQUESTED')+1
  ordered[position:position]=['HOME_SDK_DRAIN_BEGIN','PLAYER_SERVICE_DRAIN_THREADS_PASS','HOME_SDK_DRAIN_FINISHED']
 if options.diagnostic_candidate:ordered=[s.replace('GRAPHICS','DIAGNOSTICS') for s in ordered]
 if options.unresponsive_app_fixture:ordered=['HOME_DEACTIVATED','SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE LAUNCHER RELEASED','GUEST_UNRESPONSIVE_APP_READY','HOME_STOP_APP_REQUESTED','HOME_UNRESPONSIVE_CHILD_REAPED','LIVE_MANAGER_RETURN_CONFIRMED','GUEST_MANAGER_STOP_AFTER_COMPLETION']
 if options.launcher_failure:ordered=[s for s in ordered if not s.startswith('SYSTEM_DEVICE ')]
 position=0;order_ok=True
 for marker in ordered:
  found=output.find(marker,position)
  if found<0:order_ok=False;break
  position=found+len(marker)
 events=['SYSTEM_DEVICE '+role+' '+event for role,event in re.findall(r'SYSTEM_DEVICE (LAUNCHER|GRAPHICS|DIAGNOSTICS) (REOPEN|RELEASED|OPEN|FRAME|PROC_STATUS_VALIDATED)',output)]
 expected=['SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER RELEASED','SYSTEM_DEVICE GRAPHICS OPEN','SYSTEM_DEVICE GRAPHICS FRAME','SYSTEM_DEVICE GRAPHICS FRAME','SYSTEM_DEVICE GRAPHICS RELEASED','SYSTEM_DEVICE LAUNCHER REOPEN','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER RELEASED']
 if options.diagnostic_candidate:
  expected=[s.replace('GRAPHICS','DIAGNOSTICS') for s in expected];expected.insert(6,'SYSTEM_DEVICE DIAGNOSTICS PROC_STATUS_VALIDATED')
 if options.launcher_failure:expected=[]
 report['scope']='Original sysmgrd and appproxy with unchanged launcher/graphics, C Home protocol client, simulated devices and RAM volumes; not Sony GUI or hardware qualification'
 if options.diagnostic_candidate:
  report['scope']='Original sysmgrd/appproxy and prepared candidate launcher/Device Check with all three external app entries; C Home client and virtual devices, not Sony GUI qualification'
  report['candidate_upg_sha256']=hashlib.sha256((composition/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes()).hexdigest()
  report['candidate_diagnostics_sha256']=hashlib.sha256((composition/'external/HOMEBREW/apps/diagnostics/app').read_bytes()).hexdigest()
  report['candidate_launcher_sha256']=hashlib.sha256((composition/'external/HOMEBREW/launcher/app').read_bytes()).hexdigest()
  report['guest_proc_root_injected']=False;report['candidate_bytes_modified']=False;report['ready_to_flash']=False
  if options.launcher_failure:
   report['scope']='Original manager/proxy handles guest-only missing/invalid/crashing external launcher and returns to C Home client; candidate itself unchanged, not Sony GUI qualification'
   report['candidate_launcher_executed']=False
 if options.unresponsive_app_fixture:
  expected=['SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER RELEASED']
  report['guest_app_fault_injected']=True;report['candidate_diagnostics_executed']=False
  report['guest_fault_app_sha256']=hashlib.sha256(fault_app.read_bytes()).hexdigest()
  report['scope']='Candidate launcher with original manager/proxy handles guest-only SIGTERM-ignoring child, returns to C Home client; virtual hardware, not Sony GUI qualification'
 report['passed']=observed and not timed_out and order_ok and events==expected and 'PANIC at' not in output and 'Kernel panic' not in output
 if options.launcher_failure=='crash':report['passed']=report['passed'] and 'GUEST_LAUNCHER_CRASH_FIXTURE' in output
 report['events']=events;report['protocol_lifecycle_order_checked']=order_ok
 report['home_switch_mode']=options.home_switch_mode
 report['home_sdk_drain_fixture']=options.home_sdk_drain_fixture
 report['resident_sdk_fixture']=options.resident_sdk_fixture
 if options.resident_sdk_fixture:
  report['resident_public_sdk_pass']='RESIDENT_PUBLIC_SDK_ROUNDTRIP_PASS' in output and 'PUBLIC_MANAGED_ARM_CHANNEL_PASS' in output
  report['passed']=report['passed'] and report['resident_public_sdk_pass']
  report['sdk_client_and_host_original_libc_arm']=True
  report['sdk_player_backend_modeled']=True
  report['sdk_delivery_policy']='Fixture-only explicit socketpair/SCM_RIGHTS and designated inherited child descriptor; not original-manager grant authorization'
 report['resident_restart_fixture']=options.resident_restart_fixture
 if options.resident_restart_fixture:
  report['resident_registrations']=output.count('RESIDENT_REGISTERED 65552')
  report['resident_restart_request_accepted']='HOME_RESIDENT_START_ACCEPTED' in output
  report['passed']=report['passed'] and report['resident_restart_request_accepted'] and report['resident_registrations']>=2
 report['resident_exit_code']=options.resident_exit_code
 report['resident_exit_fixture']=options.resident_exit_fixture
 if options.resident_exit_fixture:
  report['resident_registered_before_exit']='RESIDENT_REGISTERED 65552' in output
  report['resident_exit_observed']='RESIDENT_NORMAL_EXIT' in output
  assert report['resident_registered_before_exit'] and report['resident_exit_observed']
 report['missing_resident_fixture']=options.missing_resident_fixture
 if options.missing_resident_fixture:
  report['resident_executable_present']=False
  report['resident_registration_observed']='RESIDENT_REGISTERED' in output
  assert not report['resident_registration_observed']
 report['resident_fixture']=options.resident_fixture
 if options.resident_fixture:
  resident_pids=re.findall(r'HOME_RESIDENT_ALIVE (\d+)',output)
  assert len(resident_pids)>=2 and len(set(resident_pids))==1,output[-2000:]
  assert 'RESIDENT_REGISTERED 65552' in output
  assert output.count('RESIDENT_REGISTERED 65552')==1
  report['resident_pid_stable']=True;report['resident_pid']=int(resident_pids[0])
  report['resident_parent_exec']=re.search(r'RESIDENT_PARENT_EXEC ([^\r\n]+)',output).group(1)
  resident_parent=int(re.search(r'RESIDENT_REGISTERED 65552 PID \d+ PPID (\d+)',output).group(1))
  home_parents=[int(value) for value in re.findall(r'HOME_PARENT_PID (\d+)',output)]
  assert home_parents and all(pid==resident_parent for pid in home_parents) and report['resident_parent_exec']=='/usr/local/bin/sysmgrd'
  report['resident_same_manager_parent']=True;report['resident_manager_pid']=resident_parent
 report['home_quit_delay_ms']=options.home_quit_delay_ms
 if options.home_quit_delay_ms:
  assert 'HOME_QUIT_DELAY_BEGIN '+str(options.home_quit_delay_ms) in output
  assert 'HOME_QUIT_DELAY_FINISHED' in output
  elapsed=re.search(r'HOME_QUIT_DELAY_FINISHED (\d+)',output)
  assert elapsed and int(elapsed.group(1))>=options.home_quit_delay_ms
  report['home_quit_measured_delay_ms']=int(elapsed.group(1))
 if options.home_switch_mode:
  report['scope']='Original manager/proxy mode1 quits and relaunches C Home client around test launcher/graphics; real process lifecycle, virtual devices, not SpiderApp qualification'
  report['home_process_restarted']="HOME_RESTART_CONFIRMED" in output;report['passed']=report['passed'] and report['home_process_restarted']
 if options.home_sdk_drain_fixture:
  report['scope']='Original manager/proxy notice4 with production SDK drain and actual reader threads inside C Home client; native media/continuation and hardware remain models'
  report['sdk_drain_before_launcher_checked']=order_ok and 'HOME_SDK_DRAIN_FINISHED' in output
 report['process_calls_interposed']=bool(options.player_bootstrap_fixture);report['ipc_interposed']=False
 if options.player_bootstrap_fixture:
  report['player_bootstrap_fixture']=True;report['process_lifecycle_calls_interposed']=False;report['ready_to_flash']=False
  report['scope']='Original manager/proxy with opt-in C exec bootstrap and actual player DSO; C Home protocol payload, pinned test apps and virtual devices/RAM volumes, not SpiderApp/hardware qualification'
  report['player_library_sha256']=player_report['library_sha256'];report['passed']=report['passed'] and 'HOME_PLAYER_PRELOAD_CONFIRMED' in output
(work/'system-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print((work/'serial.log').read_text(errors='replace')[-6000:]);print((work/'qemu.log').read_text(errors='replace')[-1000:])
if options.live_manager_fixture:assert report['passed'], 'Read the actual failure log; no lifecycle pass claimed.'
