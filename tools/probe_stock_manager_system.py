"""Bounded generic ARM Linux startup of unchanged Sony sysmgrd; PC only."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,re,stat,struct,subprocess,tarfile,time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--normal-boot-fixture',action='store_true');parser.add_argument('--ram-state-fixture',action='store_true');parser.add_argument('--live-manager-fixture',action='store_true');parser.add_argument('--stock-home-fixture',action='store_true');parser.add_argument('--omf-ram-fixture',action='store_true');parser.add_argument('--stock-env-fallback-fixture',action='store_true');parser.add_argument('--empty-serial-fixture',action='store_true');parser.add_argument('--diagnostic-candidate');parser.add_argument('--launcher-failure',choices=['missing','invalid','crash']);parser.add_argument('--unresponsive-app-fixture',action='store_true');options=parser.parse_args()
if options.diagnostic_candidate:assert options.live_manager_fixture
if options.launcher_failure:assert options.diagnostic_candidate
if options.unresponsive_app_fixture:assert options.diagnostic_candidate and not options.launcher_failure
if options.live_manager_fixture:assert options.normal_boot_fixture and options.ram_state_fixture
if options.stock_home_fixture:assert options.normal_boot_fixture and options.ram_state_fixture and not options.live_manager_fixture
if options.omf_ram_fixture:assert options.stock_home_fixture
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
if options.ram_state_fixture:flags.insert(0,'-DHB_RAM_STATE')
if options.live_manager_fixture:flags.insert(0,'-DHB_LIVE_MANAGER')
if options.omf_ram_fixture:flags.insert(0,'-DHB_OMF_PARAM_RAM')
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
if options.live_manager_fixture:
 configuration=work/'AppList.conf'
 configuration.write_text('0x00000001 * /usr/local/bin/test-home\n0x00000002 * /usr/local/bin/test-responder\n0x00030001 * /contents/HOMEBREW/launcher/app --native\n')
 client_source=ROOT/'tools/fixtures/manager_home_client.c';client=work/'home-client.arm'
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,*(['-DHB_UNRESPONSIVE_APP_FIXTURE'] if options.unresponsive_app_fixture else []),'-no-pie','-fno-pie',str(client_source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(client)],cwd=ROOT,check=True)
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
report['environment_fallback_fixture']='0x05020004 (stock short-read fallback, not measured device NVP)' if options.stock_env_fallback_fixture else None
report['serial_fixture']='empty file, original short-read fallback' if options.empty_serial_fixture else None
if options.stock_home_fixture:report['scope']='Unmodified SpiderApp with stock rootfs files, minimal test AppList, simulated manager devices and RAM state volumes; startup observation only, not Sony GUI qualification'
report['test_home_client_not_sony_gui']=options.live_manager_fixture
report['diagnostic_candidate']=options.diagnostic_candidate
report['guest_launcher_failure_fixture']=options.launcher_failure
report['live_return_observed']=b'LIVE_MANAGER_RETURN_CONFIRMED' in (work/'serial.log').read_bytes()
if options.live_manager_fixture:
 output=(work/'serial.log').read_text(errors='replace')
 ordered=['HOME_CLIENT_STARTED','HOME_REPLY 0 0 0','HOME_REPLY 1 1 0','HOME_REPLY 2 36 0','HOME_REPLY 3 6 0','HOME_DEACTIVATED','SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE GRAPHICS OPEN','SYSTEM_DEVICE GRAPHICS RELEASED','SYSTEM_DEVICE LAUNCHER REOPEN','LIVE_MANAGER_RETURN_CONFIRMED','GUEST_MANAGER_STOP_AFTER_COMPLETION']
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
 report['process_calls_interposed']=False;report['ipc_interposed']=False
(work/'system-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print((work/'serial.log').read_text(errors='replace')[-6000:]);print((work/'qemu.log').read_text(errors='replace')[-1000:])
if options.live_manager_fixture:assert report['passed'], 'Read the actual failure log; no lifecycle pass claimed.'
