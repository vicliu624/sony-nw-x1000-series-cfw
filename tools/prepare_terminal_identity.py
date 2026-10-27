"""Explicit PC pairing setup; private identity is never distributed in a release."""
from pathlib import Path
import argparse,hashlib,os,subprocess,tempfile
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--player',type=Path,required=True,help='mounted visible player-storage root');p.add_argument('--computer',type=Path,required=True,help='new/private PC pairing directory');a=p.parse_args()
 root=a.player.resolve();app=root/'HOMEBREW/apps/terminal/app.ini'
 if not app.is_file() or '\nid=terminal\n' not in '\n'+app.read_text(encoding='ascii'):raise ValueError('Install WiFi Terminal on this visible storage first')
 private=root/'HOMEBREW/data/terminal'
 for path in (root/'HOMEBREW',root/'HOMEBREW/data',private):
  if path.is_symlink():raise ValueError('Refusing a linked identity directory')
  path.mkdir(exist_ok=True)
  if not path.resolve().is_relative_to(root):raise ValueError('Identity directory escapes selected player storage')
 names=('server-key.der','server-cert.der')
 if any((private/n).exists() for n in names):raise FileExistsError('Existing pairing retained; explicitly remove it to rotate identity')
 pc=a.computer.resolve();pc.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='x1060-pairing-',dir=pc) as temporary:
  work=Path(temporary);key=work/'key.pem';certificate=work/'certificate.pem'
  subprocess.run(['openssl','ecparam','-name','prime256v1','-genkey','-noout','-out',str(key)],check=True)
  subprocess.run(['openssl','req','-new','-x509','-sha256','-days','3650','-key',str(key),'-subj','/CN=X1060 WiFi Terminal/','-out',str(certificate)],check=True)
  subprocess.run(['openssl','ec','-in',str(key),'-outform','DER','-out',str(work/'server-key.der')],check=True,capture_output=True)
  subprocess.run(['openssl','x509','-in',str(certificate),'-outform','DER','-out',str(work/'server-cert.der')],check=True)
  for name in names:
   data=(work/name).read_bytes()
   with (private/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   if (private/name).read_bytes()!=data:raise OSError('Identity readback mismatch')
  (pc/'server-cert.sha256').write_text(hashlib.sha256((work/'server-cert.der').read_bytes()).hexdigest()+'\n',encoding='ascii')
 print('Paired. Keep the PC fingerprint private, eject USB, then open WiFi Terminal. No system files were changed.')
if __name__=='__main__':main()
