"""Isolated PC ARM guest shared by player ABI tests; no physical IO passthrough."""
from pathlib import Path
import gzip,hashlib,os,stat,subprocess,time
from app_registry import ROOT
def stock_libraries(include_rt=False,include_dl=False):
 lib=ROOT/'work/arm-signal-tests/lib';res=ROOT/'work/stock-resolver-probe'
 files={'libc.so.6':lib/'libc.so.6','ld-linux.so.3':lib/'ld-linux.so.3','libpthread.so.0':res/'libpthread.so.0'}
 expected={'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de','libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474','librt.so.1':'be0149f8297952ba0dc9ea7aa98f0e2f9d21b6f697af22bf7c1ef776823dba22'}
 if include_rt:files['librt.so.1']=res/'librt.so.1'
 if include_dl:
  files['libdl.so.2']=ROOT/'work/player-sqlite-ro/libdl.so.2';expected['libdl.so.2']='95e1b346e04a0270d72c2bc45f135307d52cda3a2ec27c105c2df835b16bc4f4'
 for name,path in files.items():assert hashlib.sha256(path.read_bytes()).hexdigest()==expected[name],name
 return files
def run_guest(work,init,programs,libraries,markers,timeout=30):
 kernel=ROOT/'work/arm-system-probe/vmlinuz-2.6.32-5-versatile'
 extract=ROOT/'work/qemu-system-tool/extracted';qemu=extract/'usr/bin/qemu-system-arm'
 assert hashlib.sha256(kernel.read_bytes()).hexdigest()=='73165e27d6f80536b0a803bd3e7c5735860df8c9056316be95c32ace4ebdaba9'
 assert hashlib.sha256(qemu.read_bytes()).hexdigest()=='e5dc5f9ef15a3f39d65666ae0ff8facc3ae08c97cf642dfa1164531aa91bfdfb'
 archive=bytearray();names=[]
 def add(name,data=b'',mode=stat.S_IFREG|0o755,major=0,minor=0):
  assert name not in names;names.append(name);encoded=name.encode()+b'\0';fields=[len(names),mode,0,0,1,0,len(data),0,0,major,minor,len(encoded),0]
  archive.extend(b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+encoded);archive.extend(b'\0'*((-len(archive))%4));archive.extend(data);archive.extend(b'\0'*((-len(archive))%4))
 for name in ('dev','proc','lib'):add(name,mode=stat.S_IFDIR|0o755)
 add('dev/console',mode=stat.S_IFCHR|0o600,major=5,minor=1);add('dev/null',mode=stat.S_IFCHR|0o666,major=1,minor=3);add('dev/urandom',mode=stat.S_IFCHR|0o600,major=1,minor=9)
 add('init',init.read_bytes())
 for name,path in programs.items():
  relative=Path(name);assert not relative.is_absolute() and all(p not in ('.','..') for p in relative.parts)
  for parent in reversed(relative.parents):
   directory=parent.as_posix()
   if directory!='.' and directory not in names:add(directory,mode=stat.S_IFDIR|0o755)
  add(name,path.read_bytes())
 for name,path in libraries.items():assert Path(name).name==name;add('lib/'+name,path.read_bytes())
 add('TRAILER!!!',mode=0);initrd=work/'initramfs.cpio.gz';initrd.write_bytes(gzip.compress(archive,mtime=0))
 command=[str(qemu),'-M','versatilepb','-cpu','arm926','-m','64M','-display','none','-monitor','none','-serial','stdio','-nic','none','-kernel',str(kernel),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init panic=0','-no-reboot']
 env=dict(os.environ);env['LD_LIBRARY_PATH']=str(extract/'usr/lib/x86_64-linux-gnu');env['QEMU_AUDIO_DRV']='none'
 serial=work/'serial.log';errors=work/'qemu.log';complete=False
 with serial.open('wb') as out,errors.open('wb') as err:
  process=subprocess.Popen(command,stdout=out,stderr=err,env=env);deadline=time.monotonic()+timeout
  try:
   while process.poll() is None and time.monotonic()<deadline:
    if all(m.encode() in serial.read_bytes() for m in markers):complete=True;break
    time.sleep(.1)
  finally:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait()
 artifacts=[Path(__file__),kernel,qemu,init,initrd,serial,errors,*programs.values(),*libraries.values()]
 return dict(passed=complete,physical_device_accessed=False,kernel_is_sony=False,external_network_disabled=True,guest_entries=names,command=command,guest_artifact_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts})
