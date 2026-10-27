import sys,json,hashlib,struct,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"runtime"))
from entry import discover,plan,launch,inspect_app

def fixture(root):
    folder=root/"demo";folder.mkdir();data=bytearray(64);data[:7]=b"\x7fELF\x01\x01\x01";struct.pack_into("<H",data,18,40)
    (folder/"app").write_bytes(data)
    m={"schema":1,"id":"demo","name":"Demo","target":"sony-nw-x1000-jp","executable":"app","bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"data_quota_bytes":65536}
    (folder/"app.json").write_text(json.dumps(m));return folder,m
class EntryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_discovery_and_empty_return(self):
        self.assertTrue(discover(self.root)["return_to_sony"]);fixture(self.root);self.assertEqual(len(discover(self.root)["apps"]),1)
    def test_plan_never_enables_execution(self):
        f,m=fixture(self.root);self.assertEqual(plan(inspect_app(f))["status"],"blocked-before-execution")
        with self.assertRaises(RuntimeError):launch(m)
    def test_external_readiness_flag_rejected(self):
        f,m=fixture(self.root);m["verified"]=True;(f/"app.json").write_text(json.dumps(m));self.assertFalse(discover(self.root)["apps"])
    def test_path_escape_rejected(self):
        f,m=fixture(self.root);m["executable"]="../../bin/sh";(f/"app.json").write_text(json.dumps(m));self.assertFalse(discover(self.root)["apps"])
    def test_oversized_quota_rejected(self):
        f,m=fixture(self.root);m["data_quota_bytes"]=2**40;(f/"app.json").write_text(json.dumps(m));self.assertFalse(discover(self.root)["apps"])
    def test_corrupt_program_rejected(self):
        f,m=fixture(self.root);(f/"app").write_bytes(bytes(64));self.assertFalse(discover(self.root)["apps"])
    def test_symlink_program_rejected(self):
        f,m=fixture(self.root);(f/"app").rename(f/"other");(f/"app").symlink_to("other");self.assertFalse(discover(self.root)["apps"])
    def test_duplicate_keys_rejected(self):
        f,m=fixture(self.root);s=json.dumps(m);(f/"app.json").write_text(s[:-1]+',"schema":1}');self.assertFalse(discover(self.root)["apps"])
