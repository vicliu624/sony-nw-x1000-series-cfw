"""Reject incomplete or corrupted application package resources."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_app_package import verify

class AppPackageTests(unittest.TestCase):
    def make(self,folder):
        app=bytearray(52);app[:6]=b'\x7fELF\x01\x01';app[18:20]=(40).to_bytes(2,'little')
        sha=hashlib.sha256(app).hexdigest()
        (folder/'app').write_bytes(app)
        (folder/'icon.png').write_bytes((Path(__file__).resolve().parents[1]/'runtime/native/assets/icon.png').read_bytes())
        (folder/'app.ini').write_text(f'api=1\nid=independent-test\nname=Example\nversion=1.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes=52\nsha256={sha}\n')
        (folder/'app-info.json').write_text(json.dumps(dict(id='independent-test',version='1.0.0',title='Example',summary='Example app')))
        (folder/'presentation.bin').write_bytes(b'HBART001'+b'Example'.ljust(49,b'\0')+b'Example app'.ljust(97,b'\0')+b'\0'*2592)
        self.index(folder)
    def index(self,folder):
        (folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.name}\n' for p in sorted(folder.iterdir()) if p.name!='files.sha256'))
    def test_corruption_and_unindexed_files_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);self.make(folder);self.assertTrue(verify(folder)['passed'])
            (folder/'presentation.bin').write_bytes(b'bad')
            with self.assertRaises(ValueError):verify(folder)
            self.make(folder);(folder/'unindexed').write_bytes(b'x')
            with self.assertRaises(ValueError):verify(folder)
    def test_rehashed_identity_and_presentation_mismatch_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);self.make(folder)
            info=json.loads((folder/'app-info.json').read_text());info['version']='2.0.0';(folder/'app-info.json').write_text(json.dumps(info));self.index(folder)
            with self.assertRaises(ValueError):verify(folder)
            self.make(folder);data=bytearray((folder/'presentation.bin').read_bytes());data[8]=ord('X');(folder/'presentation.bin').write_bytes(data);self.index(folder)
            with self.assertRaises(ValueError):verify(folder)
if __name__=='__main__':unittest.main()
