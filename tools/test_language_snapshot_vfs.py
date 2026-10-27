"""PC-only ARM kernel VFS mount-pinning experiment. No physical devices."""
from pathlib import Path
import subprocess,stat,gzip,json,time,os,hashlib
ROOT=Path(__file__).resolve().parents[1]
w=ROOT/'work/language-snapshot-vfs-1';w.mkdir(exist_ok=True)
lib=ROOT/'work/stock-manager-runtime-probe/root/lib';binary=w/'init.arm'
source=ROOT/'tools/fixtures/language_snapshot_vfs_init.c'
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-nostdlib','-fno-pie','-no-pie','-Wl,--hash-style=sysv',str(source),'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
a=bytearray();inode=0
def add(name,data=b'',mode=stat.S_IFREG|0o755,major=0,minor=0):
 global inode
 inode+=1;n=name.encode()+b'\0';fields=[inode,mode,0,0,1,0,len(data),0,0,major,minor,len(n),0]
 a.extend(b'070701'+b''.join(('%08x'%x).encode()for x in fields)+n);a.extend(b'\0'*(-len(a)%4));a.extend(data);a.extend(b'\0'*(-len(a)%4))
for name in ['dev','contents','lib']:add(name,mode=stat.S_IFDIR|0o755)
add('dev/console',mode=stat.S_IFCHR|0o600,major=5,minor=1)
add('init',binary.read_bytes())
for name in ['libc.so.6','ld-linux.so.3']:add('lib/'+name,(lib/name).read_bytes())
add('TRAILER!!!');initrd=w/'initramfs.cpio.gz';initrd.write_bytes(gzip.compress(a,mtime=0))
qemu=ROOT/'work/qemu-system-tool/extracted/usr/bin/qemu-system-arm';kernel=ROOT/'work/arm-system-probe/vmlinuz-2.6.32-5-versatile'
cmd=[str(qemu),'-M','versatilepb','-cpu','arm926','-m','64M','-display','none','-monitor','none','-serial','stdio','-nic','none','-kernel',str(kernel),'-initrd',str(initrd),'-append','console=ttyAMA0 rdinit=/init panic=0','-no-reboot']
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(ROOT/'work/qemu-system-tool/extracted/usr/lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
with (w/'serial.log').open('wb')as out,(w/'qemu.log').open('wb')as err:
 p=subprocess.Popen(cmd,stdout=out,stderr=err,env=env);deadline=time.monotonic()+25;observed=False
 while time.monotonic()<deadline and p.poll()is None:
  if b'SNAPSHOT_VFS_COMPLETE' in (w/'serial.log').read_bytes():observed=True;break
  time.sleep(.1)
 if p.poll()is None:p.terminate()
 try:p.wait(timeout=3)
 except subprocess.TimeoutExpired:p.kill();p.wait()
log=(w/'serial.log').read_text(errors='replace');passed=observed and 'SNAPSHOT_VFS_PASS' in log and 'SNAPSHOT_VFS_FAIL' not in log
r={'passed':passed,'physical_device_access':False,'scope':'Real ARM Linux2.6.32 VFS and Sony libc; tmpfs fixture, not Sony2.6.10 VFAT/power hardware; no actual suspend. File mapping alone pins mount after fd close; anonymous copy permits unmount and data access.','cycles':32 if passed else 0,'source_hashes':{str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in [Path(__file__),source,binary,kernel,initrd,lib/'libc.so.6',lib/'ld-linux.so.3']},'command':cmd}
(w/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(log[-2200:]);print((w/'qemu.log').read_text(errors='replace')[-500:]);assert passed
