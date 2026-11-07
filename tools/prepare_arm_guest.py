"""Install verified local PC QEMU/kernel inputs under work; never accesses a player.

Supply an extracted Ubuntu Noble QEMU 8.2.2-0ubuntu1.18 runtime (including its
shared-library dependencies) and the archived Debian squeeze6 ARM kernel deb.
No downloads, package-manager installation, firmware packaging or guest launch.
"""
import argparse,hashlib,json,subprocess,tarfile,io
from pathlib import Path
from app_registry import ROOT

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--kernel-package',type=Path,required=True)
 p.add_argument('--qemu-root',type=Path,required=True)
 a=p.parse_args();package=a.kernel_package.resolve();source=a.qemu_root.resolve()
 if not package.is_relative_to(ROOT/'work') or not source.is_relative_to(ROOT/'work'):
  raise ValueError('Use local inputs under work')
 if digest(package.read_bytes())!='ec13c3553c3bf187b40775360b04959cebe13aeeccd7ec2e3acd9f3c20f1c3d4':
  raise ValueError('Expected pinned Debian 2.6.32-48squeeze6 armel package')
 executable=source/'usr/bin/qemu-system-arm'
 if digest(executable.read_bytes())!='e5dc5f9ef15a3f39d65666ae0ff8facc3ae08c97cf642dfa1164531aa91bfdfb':
  raise ValueError('Expected pinned Ubuntu QEMU executable')
 archive=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)])
 with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as t:
  kernel=t.extractfile('./boot/vmlinuz-2.6.32-5-versatile').read()
 if digest(kernel)!='1af9b9649bccce019f16d9177be3d3c344585368ea60055d3407c07e30b208d2':
  raise ValueError('Kernel payload mismatch')
 pending={ROOT/'work/arm-system-probe/vmlinuz-2.6.32-5-versatile':kernel}
 destination=ROOT/'work/qemu-system-tool/extracted'
 files=[executable,*sorted((source/'usr/lib/x86_64-linux-gnu').glob('*.so*'))]
 for path in files:
  if not path.resolve().is_relative_to(source):raise ValueError('Runtime symlink escapes input tree')
  if path.is_file():pending[destination/path.relative_to(source)]=path.read_bytes()
 # Validate every destination before writing anything. Preserve unrelated inputs.
 for path,data in pending.items():
  if not path.resolve().is_relative_to(ROOT/'work') or (path.is_symlink() and not path.exists()):raise ValueError('Unsafe output path')
  if path.exists() and path.read_bytes()!=data:raise ValueError('Different existing input: '+str(path))
 for path,data in pending.items():
  path.parent.mkdir(parents=True,exist_ok=True)
  if not path.exists():path.write_bytes(data)
  if path.name=='qemu-system-arm':path.chmod(0o755)
 report=dict(prepared=True,kernel_profile='debian-2.6.32-48squeeze6',device_accessed=False,
  source_package_sha256=digest(package.read_bytes()),
  files={path.relative_to(ROOT).as_posix():digest(data) for path,data in pending.items()})
 receipt=ROOT/'work/qemu-system-tool/prepared.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
