"""Build read-only original-radio fingerprints from the exact local image."""
import hashlib
from marvell_firmware import parse

ORIGINAL_SHA='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
RANGES=((0x8078,64),(0x88d4,64),(0xa314,64),(0x136b0,64),
        (0x163ec,16),(0xc00026b0,4))


def fingerprint(blob):
    if hashlib.sha256(blob).hexdigest()!=ORIGINAL_SHA:raise ValueError('unqualified original radio')
    memory={r.address+i:b for r in parse(blob) if r.command==1 for i,b in enumerate(r.data)}
    data=b''.join(bytes(memory[base+i] for i in range(size)) for base,size in RANGES)
    return hashlib.sha256(data).hexdigest(),memory


def fixture_header(blob):
    digest,memory=fingerprint(blob)
    words=[(base+i,int.from_bytes(bytes(memory[base+i+j] for j in range(4)),'little'))
           for base,size in RANGES for i in range(0,size,4)]
    return ('/* PC-test-only original words; never ship in the native SDK. */\n'
            'static const unsigned stock_fixture_words[][2]={'+
            ','.join('{0x%xu,0x%xu}'%pair for pair in words)+'};\n')


if __name__=='__main__':
    from pathlib import Path
    digest,_=fingerprint(Path('work/targets-jp/sd8686.bin').read_bytes())
    print('SHA256',digest,'bytes',sum(size for _,size in RANGES))
