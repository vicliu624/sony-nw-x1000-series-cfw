"""Pinned PC tools/modules for a volatile QEMU FAT32 user-volume fixture.

Run with --prepare-inputs after placing the listed vendor packages under work.
No downloads, system package installation, player access or firmware edits.
"""
import argparse,hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
from app_registry import ROOT

AREA=ROOT/'work/stock-user-volume-inputs'
PACKAGES={
 'work/qemu-system-bootstrap/kernel.deb':'ec13c3553c3bf187b40775360b04959cebe13aeeccd7ec2e3acd9f3c20f1c3d4',
 'work/fat-pc-tools/dosfstools_4.2-1.1build1_amd64.deb':'ace1ecc42b4d842f8e7a931933824a626dcdb7d4916470833f330ccad82afd63',
 'work/fat-pc-tools/mtools_4.0.43-1build1_amd64.deb':'deb50411c17b001c2400dd8a0146f39d12070a2fe5e92d734b1c6d0e73119262',
}
MODULES=('nls_base.ko','nls_cp437.ko','nls_iso8859-1.ko','nls_utf8.ko','fat.ko','vfat.ko')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare_inputs():
 pending={}
 for name,expected in PACKAGES.items():
  package=ROOT/name
  if package.is_symlink() or digest(package)!=expected:raise ValueError('Pinned package mismatch: '+name)
  raw=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(package)])
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tar:
   if name.endswith('/kernel.deb'):
    for module in MODULES:
     matches=[m for m in tar if m.isfile() and m.name.endswith('/'+module)]
     if not matches and module=='nls_base.ko':continue # Built into this kernel.
     if len(matches)!=1:raise ValueError('Missing/ambiguous module: '+module)
     pending[AREA/module]=tar.extractfile(matches[0]).read()
   else:
    for leaf in (('mkfs.fat',) if 'dosfstools_' in name else ('mcopy','mmd')):
     member=next(m for m in tar.getmembers() if (m.isfile() or m.issym() or m.islnk()) and m.name.endswith('/'+leaf))
     pending[AREA/leaf]=tar.extractfile(member).read()
 for path,data in pending.items():
  if not path.resolve().is_relative_to(ROOT/'work') or path.is_symlink():raise ValueError('Unsafe fixture input output')
  if path.exists() and path.read_bytes()!=data:raise ValueError('Different existing input: '+str(path))
 AREA.mkdir(parents=True,exist_ok=True)
 for path,data in pending.items():
  if not path.exists():path.write_bytes(data)
  if path.suffix!='.ko':path.chmod(0o755)
 receipt=dict(prepared=True,physical_device_access=False,packages=PACKAGES,
  files={p.name:digest(p) for p in pending},source_sha256=digest(Path(__file__)))
 (AREA/'inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt

def verified_inputs():
 receipt=json.loads((AREA/'inputs.json').read_text())
 if receipt['packages']!=PACKAGES or receipt['source_sha256']!=digest(Path(__file__)):raise ValueError('Prepare current user-volume inputs')
 expected={*MODULES,'mkfs.fat','mcopy','mmd'}
 if not expected-{'nls_base.ko'}<=set(receipt['files'])<=expected:raise ValueError('Unexpected user-volume inputs')
 for name,sha in receipt['files'].items():
  p=AREA/name
  if p.is_symlink() or digest(p)!=sha:raise ValueError('Changed user-volume input: '+name)
 return {name:AREA/name for name in receipt['files']}

def build_image(output,launcher=None):
 if not output.resolve().is_relative_to(ROOT/'work') or output.exists():raise ValueError('Use a new private work image')
 inputs=verified_inputs()
 with output.open('xb') as file:file.truncate(64*1024*1024)
 subprocess.run([str(inputs['mkfs.fat']),'-F','32','-s','1','-i','10000001','-n','QEMU_ONLY',str(output)],check=True,capture_output=True)
 if launcher is not None:
  env={**os.environ,'MTOOLSRC':'/dev/null'}
  subprocess.run([str(inputs['mmd']),'-i',str(output),'::HOMEBREW','::HOMEBREW/launcher'],env=env,check=True,capture_output=True)
  subprocess.run([str(inputs['mcopy']),'-i',str(output),str(launcher),'::HOMEBREW/launcher/app'],env=env,check=True,capture_output=True)
 return inputs

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-inputs',action='store_true',required=True);parser.parse_args()
 print(json.dumps(prepare_inputs(),indent=2))
