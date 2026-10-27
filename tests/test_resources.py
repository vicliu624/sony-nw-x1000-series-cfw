import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from resources import parse_stx,parse_tgp,STX_MAGIC

def stx():
    b=bytearray(64);b[:len(STX_MAGIC)]=STX_MAGIC;struct.pack_into("<II",b,44,56,2);struct.pack_into("<II",b,56,64,68);return bytes(b)+"是\0No\0".encode("utf-16-le")
def tgp():
    b=bytearray(80);b[:8]=b"TGP\0\1\0\0\0";struct.pack_into(">II",b,8,32,1);struct.pack_into(">I",b,28,80);b[32:36]=b"TXD\0";struct.pack_into(">7I",b,36,1,1,16,0,0,0,4);return bytes(b)
class ResourceTests(unittest.TestCase):
    def test_stx_unicode_and_index(self):self.assertEqual(parse_stx(stx()),["是","No"])
    def test_stx_null_pointer_is_absent(self):
        b=bytearray(stx());struct.pack_into("<I",b,56,0)
        self.assertEqual(parse_stx(b),["","No"])
    def test_stx_bad_offset(self):
        b=bytearray(stx());struct.pack_into("<I",b,56,1)
        with self.assertRaises(ValueError):parse_stx(b)
    def test_stx_unterminated(self):
        with self.assertRaises(ValueError):parse_stx(stx()[:-2])
    def test_tgp_bounds(self):self.assertEqual(parse_tgp(tgp())[0]["format"],16)
    def test_tgp_wrong_size(self):
        with self.assertRaises(ValueError):parse_tgp(tgp()[:-1])
    def test_tgp_wrong_pixel_length(self):
        b=bytearray(tgp());struct.pack_into(">I",b,60,8)
        with self.assertRaises(ValueError):parse_tgp(b)
if __name__=="__main__":unittest.main()
