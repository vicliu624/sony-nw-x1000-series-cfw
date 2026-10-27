import sys,hashlib,struct,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"runtime"))
from catalog import scan

def app(root,id,name="Demo"):
    p=root/id;p.mkdir();b=bytearray(96);b[:7]=b"\x7fELF\x01\x01\x01";struct.pack_into("<HH",b,16,2,40);(p/"app").write_bytes(b)
    fields={"api":"1","id":id,"name":name,"version":"0.1.0","target":"sony-nw-x1000-jp","exec":"app","bytes":str(len(b)),"sha256":hashlib.sha256(b).hexdigest()}
    (p/"app.ini").write_text("\n".join(k+"="+v for k,v in fields.items())+"\n");return p
class CatalogTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_store_first(self):
        app(self.root,"demo","A demo");app(self.root,"store","Store");r=scan(self.root);self.assertEqual([a['id']for a in r['apps']],["store","demo"])
    def test_empty_keeps_return(self):self.assertTrue(scan(self.root)['return_to_walkman']);self.assertFalse(scan(self.root)['store_installed'])
    def test_invalid_target(self):
        p=app(self.root,"demo");f=p/'app.ini';f.write_text(f.read_text().replace('sony-nw-x1000-jp','sony-a918'));self.assertFalse(scan(self.root)['apps'])
    def test_staging_ignored(self):
        (self.root/'.install-store').mkdir();self.assertFalse(scan(self.root)['apps'])
    def test_hash_failure(self):
        p=app(self.root,"demo");(p/'app').write_bytes(bytes(96));self.assertFalse(scan(self.root)['apps'])
    def test_windows_crlf(self):
        p=app(self.root,"demo");f=p/'app.ini';f.write_bytes(f.read_bytes().replace(b'\n',b'\r\n'));self.assertEqual(len(scan(self.root)['apps']),1)
    def test_bare_cr_is_not_native_line_separator(self):
        p=app(self.root,"demo");f=p/'app.ini';f.write_bytes(f.read_bytes().replace(b'\n',b'\r'));self.assertFalse(scan(self.root)['apps'])
    def test_final_newline_optional(self):
        p=app(self.root,"demo");f=p/'app.ini';f.write_bytes(f.read_bytes().rstrip(b'\n'));self.assertEqual(len(scan(self.root)['apps']),1)
    def test_executable_symlink(self):
        p=app(self.root,"demo");(p/'app').rename(p/'original');(p/'app').symlink_to('original');self.assertFalse(scan(self.root)['apps'])
    def test_duplicate_fields(self):
        p=app(self.root,"demo");f=p/'app.ini';f.write_text(f.read_text()+'api=1\n');self.assertFalse(scan(self.root)['apps'])
    def test_native_manifest_byte_limit(self):
        p=app(self.root,"demo");f=p/'app.ini'
        original=f.read_bytes();padding=1024-len(original)
        f.write_bytes(original.replace(b'bytes=96',b'bytes='+b'0'*padding+b'96'))
        self.assertEqual(len(scan(self.root)['apps']),1)
        f.write_bytes(f.read_bytes().replace(b'bytes=',b'bytes=0'))
        self.assertFalse(scan(self.root)['apps'])
    def test_native_name_utf8_byte_limit(self):
        app(self.root,"fits","中"*16);app(self.root,"too-long","中"*17)
        self.assertEqual([a['id'] for a in scan(self.root)['apps']],["fits"])
    def test_native_version_byte_limit(self):
        p=app(self.root,"demo");f=p/'app.ini'
        f.write_text(f.read_text().replace('version=0.1.0','version=0.1.0-'+ 'a'*27))
        self.assertFalse(scan(self.root)['apps'])
