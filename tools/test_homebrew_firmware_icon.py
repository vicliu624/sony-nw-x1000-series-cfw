"""Audit the final UPG's Homebrew icon wiring and exact preserved textures."""
from pathlib import Path
import argparse,hashlib,io,struct,sys,tarfile
from elftools.elf.elffile import ELFFile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_tgp

def verify(path):
    _,parts=unpack(Path(path).read_bytes(),require_stock=False)
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as tar:
        image=tar.extractfile('./usr/local/bin/SpiderApp').read()
        data=tar.extractfile('./usr/local/share/GUI/skinRom/TEXGRP00.DAT').read()
    elf=ELFFile(io.BytesIO(image));loads=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
    def word(address):
        for s in loads:
            if s['p_vaddr']<=address and address+4<=s['p_vaddr']+s['p_filesz']:
                return struct.unpack_from('<I',image,s['p_offset']+address-s['p_vaddr'])[0]
        raise AssertionError('unmapped icon word')
    assert word(0x4f7930)==140,'icon catalog count regressed'
    a,b=word(0xb5984),word(0xb5988)
    assert [word(a+i*4) for i in range(11)]==[54,55,56,57,58,59,60,61,62,63,139],'Homebrew reused Settings in mode1'
    assert [word(b+i*4) for i in range(10)]==[62,54,56,57,58,59,63,61,60,139],'Homebrew reused Settings in mode2'
    records=parse_tgp(data);assert len(records)==140
    with tarfile.open(ROOT/'work/upg-jp/verified-3.bin',mode='r:gz') as original:
        stock=original.extractfile('./usr/local/share/GUI/skinRom/TEXGRP00.DAT').read()
    assert data[32:len(stock)]==stock[32:],'original texture altered'
    icon=records[139];assert (icon['width'],icon['height'],icon['format'])==(64,64,16)
    pixels=data[icon['offset']+32:icon['offset']+32+icon['bytes']]
    assert pixels==Image.open(ROOT/'assets/icons/homebrew-shadow-v2-64.png').convert('RGBA').tobytes('raw','BGRA')
    assert hashlib.sha256(data).hexdigest()=='4aefed358aa6aba176b38d7767ab71b87ed5ed7b3ba803552a1e799d13e49bf0','accepted shadow artwork changed'
    print('Final UPG: both Homebrew entries use139, catalog140, accepted shadow pixels match; original Settings/textures preserved.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('firmware',type=Path);a=p.parse_args();verify(a.firmware)
