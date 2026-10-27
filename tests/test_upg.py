import sys,struct,hashlib,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from Crypto.Cipher import DES
from upg import KEY,SIGNATURE,unpack

def fixture(overlap=False):
    header=struct.pack("<8sII",SIGNATURE,4,0)+b"".join(struct.pack("<II",64 if overlap else 64+i*8,8)for i in range(4))
    tail=DES.new(KEY,DES.MODE_ECB).encrypt(header+bytes(32))
    return hashlib.md5(tail).digest()+tail

class ContainerTests(unittest.TestCase):
    def test_valid_synthetic_layout(self):
        entries,parts=unpack(fixture(),require_stock=False)
        self.assertEqual(len(parts),4)
        self.assertEqual(entries[-1],(88,8))
    def test_unpinned_input_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError,"pinned"):
            unpack(fixture())
    def test_bad_checksum(self):
        with self.assertRaisesRegex(ValueError,"MD5"):
            unpack(bytes(16)+fixture()[16:],require_stock=False)
    def test_overlapping_layout(self):
        with self.assertRaisesRegex(ValueError,"overlapping"):
            unpack(fixture(True),require_stock=False)
    def test_truncated_input(self):
        with self.assertRaises(ValueError):
            unpack(fixture()[:-1],require_stock=False)

if __name__=="__main__":unittest.main()
