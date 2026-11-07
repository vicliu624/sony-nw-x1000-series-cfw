"""Prepare pinned original-userspace QEMU inputs; no extraction to the host root."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
from app_registry import ROOT

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 rootfs=ROOT/'work/upg-jp/verified-3.bin';gpl=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
 package=ROOT/'work/qemu-system-bootstrap/kernel.deb'
 expected=[(rootfs,'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'),
  (gpl,'286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'),
  (package,'ec13c3553c3bf187b40775360b04959cebe13aeeccd7ec2e3acd9f3c20f1c3d4')]
 for path,digest in expected:
  if sha(path.read_bytes())!=digest:raise ValueError('Unverified source: '+str(path))
 pending={};base=ROOT/'work/stock-manager-runtime-probe/root'
 with tarfile.open(rootfs,'r:gz') as t:
  for name in ('ld-linux.so.3','libc.so.6','libpthread.so.0','libresolv.so.2','libdl.so.2','librt.so.1'):
   pending[base/'lib'/name]=t.extractfile('./lib/'+name).read()
  for name in ('usr/local/bin/sysmgrd','usr/local/bin/appproxy','etc/AppList.conf','etc/passwd','etc/group','lib/modules/icx1087_power.ko'):
   pending[base/name]=t.extractfile('./'+name).read()
 with tarfile.open(gpl,'r:gz') as t:
  mappings={
   'drivers/char/mp200_pm_ext.c':'manager-pm-source/drivers_char_mp200_pm_ext.c',
   'include/asm-arm/arch-mp200/mp200_pm_ext.h':'manager-pm-source/include_asm-arm_arch-mp200_mp200_pm_ext.h',
   'icx1087_power.h':'manager-power-source/icx1087_power.h',
   'icx1087_cradle.h':'manager-power-source/icx1087_cradle.h',
   'icx1087_cradle.c':'manager-power-source/icx1087_cradle.c',
   'mp201_mem.h':'manager-power-source/mp201_mem.h',
   'include/asm-arm/arch-mp200/memory.h':'manager-power-source/memory.h',
   'include/asm-arm/arch-mp200/hardware.h':'stock-dsp-source/include/asm-arm/arch-mp200/hardware.h',
   'include/asm-arm/arch-mp200/inter_dsp.h':'stock-dsp-source/include/asm-arm/arch-mp200/inter_dsp.h',
   'include/asm-arm/arch-mp200/inter_dsp_ioctl.h':'stock-dsp-source/include/asm-arm/arch-mp200/inter_dsp_ioctl.h',
   'arch/arm/mach-mp200/inter_dsp.c':'stock-dsp-source/arch/arm/mach-mp200/inter_dsp.c',
   'include/asm-arm/arch-mp200/icx1087_audio.h':'stock-ui-source/icx1087_audio.h',
   'include/asm-arm/arch-mp200/icx1087_beep.h':'stock-ui-source/icx1087_beep.h',
   'include/asm-arm/arch-mp200/fbcommon.h':'stock-ui-source/fbcommon.h',
   'include/asm-arm/arch-mp200/icx_touch_screen.h':'stock-ui-source/icx_touch_screen.h',
   'include/asm-arm/arch-mp200/icx_watch_elapsed_time.h':'stock-ui-source/icx_watch_elapsed_time.h',
   'drivers/char/icx_watch_elapsed_time.c':'stock-ui-source/icx_watch_elapsed_time.c'}
  for suffix,destination in mappings.items():
   matches=[m for m in t.getmembers() if m.isfile() and m.name.endswith('/'+suffix)]
   if len(matches)!=1:raise ValueError('Ambiguous/missing GPL source: '+suffix)
   pending[ROOT/'work'/destination]=t.extractfile(matches[0]).read()
 archive=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)])
 block=ROOT/'work/arm-block-kernel';rows=[]
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as t:
  for name in ('brd.ko','mbcache.ko','ext2.ko','evdev.ko','vmlinuz-2.6.32-5-versatile'):
   matches=[m for m in t.getmembers() if m.isfile() and m.name.endswith('/'+name)]
   if len(matches)!=1:raise ValueError('Missing Debian kernel component: '+name)
   data=t.extractfile(matches[0]).read();pending[block/name]=data;rows.append(dict(name=name,sha256=sha(data)))
 pending[block/'inputs.json']=(json.dumps(dict(files=rows,kernel_profile='debian-2.6.32-48squeeze6',source_package_sha256=sha(package.read_bytes())),indent=2)+'\n').encode()
 refresh_manifests=set()
 for path,data in pending.items():
  if not path.resolve().is_relative_to(ROOT/'work') or path.is_symlink():raise ValueError('Unsafe destination')
  if path.exists() and path.read_bytes()!=data:
   if path==block/'inputs.json':
    old=json.loads(path.read_text());new=json.loads(data)
    names={r['name']:r for r in new['files']}
    if old.get('kernel_profile')==new['kernel_profile'] and old.get('source_package_sha256')==new['source_package_sha256'] and all(names.get(r['name'])==r for r in old['files']):
     refresh_manifests.add(path);continue
   raise ValueError('Different existing input: '+str(path))
 for path,data in pending.items():
  path.parent.mkdir(parents=True,exist_ok=True)
  if not path.exists() or path in refresh_manifests:path.write_bytes(data)
  if path.name in ('ld-linux.so.3','sysmgrd','appproxy'):path.chmod(0o755)
 report=dict(prepared=True,device_accessed=False,files={p.relative_to(ROOT).as_posix():sha(d) for p,d in pending.items()},
  source_hashes={p.relative_to(ROOT).as_posix():h for p,h in expected})
 (ROOT/'work/stock-manager-runtime-probe/inputs.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,files=len(pending),device_accessed=False),indent=2))
if __name__=='__main__':main()
