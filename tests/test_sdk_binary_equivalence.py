"""Only known non-runtime GCC file markers can differ in a migration build."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from app_registry import ROOT
from sdk_binary_equivalence import normalize_gcc_file_symbols,canonical_payload

def elf(file='ccABC123.o',function='ccFNC123.o',code=b'\0\0\xa0\xe1',allocated=False,shared=False,mapped=False):
    names=b'\0.text\0.symtab\0.strtab\0.shstrtab\0'
    strings=b'\0'+file.encode()+b'\0'+function.encode()+b'\0'
    symbols=b'\0'*16+struct.pack('<IIIBBH',1,0,0,4,0,0xfff1)+struct.pack('<IIIBBH',1 if shared else len(file)+2,0,4,0x12,0,1)
    data=bytearray(b'\0'*(84 if mapped else 52));offsets=[]
    for content in (code,symbols,strings,names):
        while len(data)%4:data.append(0)
        offsets.append(len(data));data.extend(content)
    while len(data)%4:data.append(0)
    shoff=len(data)
    data.extend(b'\0'*40)
    for values in ((1,1,6,0,offsets[0],len(code),0,0,4,0),
                   (7,2,0,0,offsets[1],len(symbols),3,2,4,16),
                   (15,3,2 if allocated else 0,0,offsets[2],len(strings),0,0,1,0),
                   (23,3,0,0,offsets[3],len(names),0,0,1,0)):
        data.extend(struct.pack('<10I',*values))
    ident=b'\x7fELF\x01\x01\x01'+b'\0'*9
    data[:52]=struct.pack('<16sHHIIIIIHHHHHH',ident,2,40,1,0,52 if mapped else 0,shoff,0,52,32 if mapped else 0,1 if mapped else 0,40,5,4)
    if mapped:data[52:84]=struct.pack('<8I',1,offsets[2],0,0,len(strings),len(strings),4,4)
    return bytes(data)

class SDKBinaryEquivalence(unittest.TestCase):
    def test_temp_file_markers_are_the_only_accepted_difference(self):
        first,records=normalize_gcc_file_symbols(elf())
        second,_=normalize_gcc_file_symbols(elf(file='ccXYZ789.o'))
        self.assertEqual(first,second);self.assertEqual(len(records),1)
        changed,_=normalize_gcc_file_symbols(elf(code=b'\x01\0\xa0\xe1'))
        self.assertNotEqual(first,changed)
        function,_=normalize_gcc_file_symbols(elf(function='ccNEW789.o'))
        self.assertNotEqual(first,function)

    def test_allocated_names_or_program_symbol_aliases_are_never_ignored(self):
        with self.assertRaises(ValueError):normalize_gcc_file_symbols(elf(allocated=True))
        with self.assertRaises(ValueError):normalize_gcc_file_symbols(elf(shared=True))
        with self.assertRaises(ValueError):normalize_gcc_file_symbols(elf(mapped=True))

    def test_digest_edges_follow_comparison_bytes_without_modifying_payload(self):
        parent=ROOT/'work/sdk-binary-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            def package(name,data,version='1.0.0'):
                folder=Path(temporary)/name;folder.mkdir()
                (folder/'app').write_bytes(data)
                manifest=('version='+version+'\nsha256='+hashlib.sha256(data).hexdigest()+'\n').encode()
                (folder/'app.ini').write_bytes(manifest)
                (folder/'files.sha256').write_text('HBFILES1\n'+''.join(hashlib.sha256(b).hexdigest()+' '+str(len(b))+' '+n+'\n' for n,b in [('app',data),('app.ini',manifest)]))
                return folder
            a=package('a',elf());b=package('b',elf(file='ccXYZ789.o'));c=package('c',elf(),version='1.0.1')
            original={p.name:p.read_bytes() for p in a.iterdir()}
            self.assertEqual(canonical_payload(a)[0],canonical_payload(b)[0])
            self.assertNotEqual(canonical_payload(a)[0],canonical_payload(c)[0])
            self.assertEqual(original,{p.name:p.read_bytes() for p in a.iterdir()})

if __name__=='__main__':unittest.main()
