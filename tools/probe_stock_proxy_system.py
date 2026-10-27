"""PC-only ARM926 system guest for stock proxy threads and socket protocol."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,re,subprocess,stat,time
ROOT=Path(__file__).resolve().parents[1]
tool=ROOT/'work/qemu-system-tool';extract=tool/'extracted'
for package in tool.glob('lib*.deb'):subprocess.run(['dpkg-deb','-x',str(package),str(extract)],check=True)
inputs=ROOT/'work/arm-system-probe';kernel=inputs/'vmlinuz-2.6.32-5-versatile'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='work/arm-system-proxy-complete');parser.add_argument('--launcher',action='store_true');parser.add_argument('--stop',action='store_true');parser.add_argument('--rounds',type=int,default=1,choices=range(1,11))
options=parser.parse_args();work=(ROOT/options.output).resolve();assert work.is_relative_to(ROOT/'work');work.mkdir(exist_ok=False)
if options.stop:assert options.launcher, '--stop requires --launcher'
assert hashlib.md5(kernel.read_bytes()).hexdigest()=='8782441dee9e950c538140ec54f52e87'
assert '8782441dee9e950c538140ec54f52e87  ./versatile/netboot/vmlinuz-2.6.32-5-versatile' in (inputs/'debian-MD5SUMS').read_text()
source=ROOT/'tools/fixtures/stock_proxy_peer.c';peer=work/'peer.arm'
lib=ROOT/'work/arm-signal-tests/lib'
flags=['-DHB_FULL_SYSTEM','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none']
if options.launcher:flags.insert(0,'-DHB_SYSTEM_LAUNCHER')
if options.stop:flags.insert(0,'-DHB_SYSTEM_STOP')
flags.insert(0,'-DHB_SYSTEM_ROUNDS='+str(options.rounds))
subprocess.run(['arm-linux-gnueabi-gcc',*flags,str(source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(peer)],cwd=ROOT,check=True)
stock=ROOT/'work/stock-manager-runtime-probe/root';proxy=stock/'usr/local/bin/appproxy'
assert hashlib.sha256(proxy.read_bytes()).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
# In-memory newc archive; no host mounts, device nodes or writable disk images.
archive=bytearray();inode=1
def add(name,data=b'',mode=stat.S_IFREG|0o755,major=0,minor=0):
 global inode
 encoded=name.encode()+b'\0'
 fields=[inode,mode,0,0,1,0,len(data),0,0,major,minor,len(encoded),0];inode+=1
 archive.extend(b'070701'+b''.join(('%08x'%n).encode() for n in fields)+encoded)
 archive.extend(b'\0'*(-len(archive)%4));archive.extend(data);archive.extend(b'\0'*(-len(archive)%4))
for name in ('dev','proc','tmp','var','run','contents','lib','usr','usr/local','usr/local/bin'):add(name,mode=stat.S_IFDIR|0o755)
add('dev/console',mode=stat.S_IFCHR|0o600,major=5,minor=1)
add('dev/null',mode=stat.S_IFCHR|0o666,major=1,minor=3)
add('init',peer.read_bytes());add('test-child',peer.read_bytes());add('usr/local/bin/appproxy',proxy.read_bytes())
names=('ld-linux.so.3','libc.so.6','libpthread.so.0','libresolv.so.2')
for name in names:add('lib/'+name,(stock/'lib'/name).read_bytes())
additional=[]
if options.launcher:
 device_source=ROOT/'tools/fixtures/system_device_preload.c';devices=work/'system-devices.so'
 subprocess.run(['arm-linux-gnueabi-gcc','-shared','-fPIC','-nostdlib','-march=armv5te','-marm','-mfloat-abi=soft','-Wl,--hash-style=sysv',str(device_source),str(lib/'libc.so.6'),str(stock/'lib/libdl.so.2'),'-o',str(devices)],check=True)
 add('lib/system-devices.so',devices.read_bytes());add('lib/libdl.so.2',(stock/'lib/libdl.so.2').read_bytes())
 composition=ROOT/'work/store-setup-workflow-fixture';manifest=json.loads((composition/'manifest.json').read_text())
 for name in ('contents/HOMEBREW','contents/HOMEBREW/launcher','contents/HOMEBREW/apps','contents/HOMEBREW/apps/graphics-demo'):add(name,mode=stat.S_IFDIR|0o755)
 for relative in ('external/HOMEBREW/launcher/app','external/HOMEBREW/apps/graphics-demo/app','external/HOMEBREW/apps/graphics-demo/app.ini'):
  path=composition/relative;row=next(row for row in manifest['files'] if row['path']==relative);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
  add(relative.replace('external/','contents/',1),path.read_bytes());additional.append(path)
 additional += [device_source,devices,stock/'lib/libdl.so.2',composition/'manifest.json']
add('TRAILER!!!',mode=0);initrd=work/'proxy-initramfs.cpio.gz';initrd.write_bytes(gzip.compress(bytes(archive),mtime=0))
qemu=extract/'usr/bin/qemu-system-arm'
command=[str(qemu),'-M','versatilepb','-cpu','arm926','-m','128M','-display','none','-monitor','none','-serial','stdio','-nic','none','-kernel',str(kernel),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init panic=0','-no-reboot']
env=dict(os.environ);env['LD_LIBRARY_PATH']=str(extract/'usr/lib/x86_64-linux-gnu');env['QEMU_AUDIO_DRV']='none'
timed_out=False;stopped_after_result=False
with (work/'serial.log').open('wb') as serial,(work/'qemu.log').open('wb') as stderr:
 process=subprocess.Popen(command,stdout=serial,stderr=stderr,env=env)
 deadline=time.monotonic()+25
 while process.poll() is None and time.monotonic()<deadline:
  if b'GUEST_PEER_RESULT ' in (work/'serial.log').read_bytes():
   stopped_after_result=True;process.terminate();break
  time.sleep(0.05)
 if process.poll() is None and not stopped_after_result:timed_out=True;process.kill()
 code=process.wait(timeout=5)
tracked=[Path(__file__),source,peer,kernel,initrd,proxy,qemu,work/'serial.log',work/'qemu.log',ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S']+[stock/'lib'/n for n in names]+additional
output=(work/'serial.log').read_bytes()
marks=[b'REGISTRATION_VALIDATED',b'ACTIVATION_CONFIRMED',b'PROXY_WAIT_STATUS 0',b'GUEST_PEER_RESULT 0',b'PROXY_ENDPOINTS_REMOVED']
if options.launcher:
 marks += [b'SYSTEM_DEVICE GRAPHICS FRAME',b'SYSTEM_DEVICE GRAPHICS RELEASED']
 marks += [b'STOP_SENT_WHILE_GRAPHICS_ACTIVE'] if options.stop else [b'SYSTEM_DEVICE LAUNCHER REOPEN']
else:marks += [b'CHILD_EXECUTED']
passed=not timed_out and stopped_after_result and all(mark in output for mark in marks) and b'Kernel panic' not in output
passed=passed and all(output.count(b'ROUND_RESULT '+str(i).encode()+b' 0')==1 for i in range(1,options.rounds+1)) and output.count(b'PROXY_ENDPOINTS_REMOVED')==options.rounds
if options.launcher:
 events=['SYSTEM_DEVICE '+role+' '+event for role,event in re.findall(r'SYSTEM_DEVICE (LAUNCHER|GRAPHICS) (REOPEN|RELEASED|OPEN|FRAME)',output.decode(errors='replace'))]
 expected=['SYSTEM_DEVICE LAUNCHER OPEN','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER RELEASED','SYSTEM_DEVICE GRAPHICS OPEN','SYSTEM_DEVICE GRAPHICS FRAME']
 expected += ['SYSTEM_DEVICE GRAPHICS RELEASED'] if options.stop else ['SYSTEM_DEVICE GRAPHICS FRAME','SYSTEM_DEVICE GRAPHICS RELEASED','SYSTEM_DEVICE LAUNCHER REOPEN','SYSTEM_DEVICE LAUNCHER FRAME','SYSTEM_DEVICE LAUNCHER RELEASED']
 passed=passed and events==expected*options.rounds and output.index(b'SYSTEM_DEVICE GRAPHICS RELEASED')<output.index(b'PROXY_WAIT_STATUS 0')
report={'scope':'Unchanged Sony appproxy in generic ARM926 Linux guest with explicit C protocol peer; not Sony kernel or hardware','passed':passed,'rounds':options.rounds,'proxy_endpoints_checked':True,'exit':code,'timed_out':timed_out,'stopped_after_result':stopped_after_result,'command':command,'physical_device_access':False,'internal_address_hooks':False,'device_io_interposed':options.launcher,'process_calls_interposed':False,'stop_while_graphics_active':options.stop,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'system-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print((work/'serial.log').read_text(errors='replace')[-10000:]);print((work/'qemu.log').read_text(errors='replace')[-2000:])
assert passed, 'Inspect the recorded guest result; no successful integration claim.'
