"""PC ARM execution of stock Sony queue, thread exit and join; no player IO."""
from pathlib import Path
import gzip,hashlib,json,os,resource,stat,subprocess,time
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-audio'
lib=ROOT/'work/arm-signal-tests/lib';res=ROOT/'work/stock-resolver-probe';shared=w/'libomf_core_os_dep.so'
assert hashlib.sha256(shared.read_bytes()).hexdigest()=='b57965fd5e04958e870a0af5d577f91b5d844b90395927d84c1dba75af905d2b'
sources=['tools/fixtures/qqmusic_stock_audio_thread.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
cmd=['arm-linux-gnueabi-gcc','-std=gnu99','-DQQ_THREAD_GUEST','-O1','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(lib),'-Wl,-rpath-link,'+str(res),*sources,'-L'+str(w),'-Wl,--no-as-needed','-lomf_core_os_dep',str(w/'libdl.so.2'),str(res/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(w/'stock-thread.arm')]
subprocess.run(cmd,cwd=ROOT,check=True)
initcmd=cmd[:]
a=initcmd.index('tools/fixtures/qqmusic_stock_audio_thread.c');initcmd[a]='tools/fixtures/qqmusic_stock_audio_guest_init.c'
a=initcmd.index('-L'+str(w));initcmd=initcmd[:a]+[str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(w/'stock-thread-init.arm')]
subprocess.run(initcmd,cwd=ROOT,check=True)
# Old Sony LinuxThreads clone ABI is rejected by qemu-user on the host.
# Run the same stock libraries under an isolated ARM Linux kernel instead.
kernel=ROOT/'work/arm-system-probe/vmlinuz-2.6.32-5-versatile'
assert hashlib.md5(kernel.read_bytes()).hexdigest()=='8782441dee9e950c538140ec54f52e87'
archive=bytearray();serial_id=1

def add(name,data=b'',mode=stat.S_IFREG|0o755,major=0,minor=0):
 global serial_id
 encoded=name.encode()+b'\0';fields=[serial_id,mode,0,0,1,0,len(data),0,0,major,minor,len(encoded),0];serial_id+=1
 archive.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+encoded)
 archive.extend(b'\0'*((-len(archive))%4));archive.extend(data);archive.extend(b'\0'*((-len(archive))%4))
for name in ('dev','proc','lib'):add(name,mode=stat.S_IFDIR|0o755)
add('dev/console',mode=stat.S_IFCHR|0o600,major=5,minor=1)
add('dev/null',mode=stat.S_IFCHR|0o666,major=1,minor=3)
add('init',(w/'stock-thread-init.arm').read_bytes())
add('test',(w/'stock-thread.arm').read_bytes())
for name,path in [('ld-linux.so.3',lib/'ld-linux.so.3'),('libc.so.6',lib/'libc.so.6'),('libpthread.so.0',res/'libpthread.so.0'),('libdl.so.2',w/'libdl.so.2'),('libomf_core_os_dep.so',shared),('omf_mc_lpcmd.so',w/'omf_mc_lpcmd.so')]:add('lib/'+name,path.read_bytes())
add('TRAILER!!!',mode=0)
initrd=w/'stock-thread-initramfs.cpio.gz';initrd.write_bytes(gzip.compress(archive,mtime=0))
extract=ROOT/'work/qemu-system-tool/extracted';qemu=extract/'usr/bin/qemu-system-arm'
env=dict(os.environ);env['LD_LIBRARY_PATH']=str(extract/'usr/lib/x86_64-linux-gnu');env['QEMU_AUDIO_DRV']='none'
command=[str(qemu),'-M','versatilepb','-cpu','arm926','-m','64M','-display','none','-monitor','none','-serial','stdio','-nic','none','-kernel',str(kernel),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init panic=0','-no-reboot']
complete=False
with (w/'stock-thread-guest.log').open('wb') as log,(w/'stock-thread-qemu.log').open('wb') as err:
 process=subprocess.Popen(command,stdout=log,stderr=err,env=env);deadline=time.monotonic()+25
 try:
  while process.poll() is None and time.monotonic()<deadline:
   if b'ORIGINAL_LPCMD_WORKER_JOINED' in (w/'stock-thread-guest.log').read_bytes() and b'STOCK_QUEUE_JOIN_COMPLETE' in (w/'stock-thread-guest.log').read_bytes():complete=True;break
   time.sleep(.1)
 finally:
  if process.poll() is None:process.terminate()
  process.wait(timeout=5)
assert complete,(w/'stock-thread-guest.log').read_text(errors='replace')[-2000:]
report={'passed':True,'original_sony_os_library_sha256':hashlib.sha256(shared.read_bytes()).hexdigest(),'original_queue_exit_join_with_real_threads':True,'original_lpcmd_command_thread_and_destroy_handle':True,'thread_start_uses_default_pthread_scheduler':True,'generic_arm_linux_guest':True,'no_sound_device_nodes_in_guest':True,'sound_device_accessed':False,'physical_device_accessed':False,'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'limits':['First worker is fixture C; second is pinned original LPCMD body and original DestroyHandle. Private component state and normal scheduling are supplied; no DSP commands execute.','Default pthread_create substitutes stock RT CreateThread policy; no real AudioC thread, DSP or kernel ownership is tested.']}
(w/'stock-thread-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
