"""QMC C port differential tests with synthetic keys/payloads, no account/audio download."""
from pathlib import Path
import base64,hashlib,importlib.util,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
reference=ROOT/'third_party/qmc-reference/qmc2_reference.py'
assert hashlib.sha256(reference.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_reference',reference);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
work=ROOT/'work/qqmusic-qmc';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)

def tea_encrypt(payload,key):
    pad=(-len(payload)-10)%8
    plain=bytes([pad])+bytes(range(1,pad+1))+b'xy'+payload+b'\0'*7
    assert len(plain)%8==0
    words=struct.unpack('>4I',key);previous=b'\0'*8;cipher_previous=b'\0'*8;out=bytearray();mask=0xffffffff
    for start in range(0,len(plain),8):
        intermediate=bytes(a^b for a,b in zip(plain[start:start+8],cipher_previous))
        a,b=struct.unpack('>2I',intermediate);total=0
        for _ in range(16):
            total=(total+0x9e3779b9)&mask
            a=(a+((((b<<4)+words[0])&mask)^((b+total)&mask)^((b>>5)+words[1])))&mask
            b=(b+((((a<<4)+words[2])&mask)^((a+total)&mask)^((a>>5)+words[3])))&mask
        encrypted=bytes(a^b for a,b in zip(struct.pack('>2I',a,b),previous))
        out.extend(encrypted);previous=intermediate;cipher_previous=encrypted
    assert ref.tencent_tea_dec(bytes(out),key)==payload
    return bytes(out)

def wrapped(raw,v2):
    tk=bytes(v for pair in zip(ref.SIMPLE_KEY,raw[:8]) for v in pair)
    v1=raw[:8]+tea_encrypt(raw[8:],tk)
    if v2:v1=ref.V2P+tea_encrypt(tea_encrypt(base64.b64encode(v1),ref.V2K2),ref.V2K1)
    encoded=base64.b64encode(v1);assert ref.derive_key(encoded)==raw
    return encoded

vectors=[]
def add(mode,encoded,raw,offset,count,label):
    source=bytes((i*29+7)%256 for i in range(count));expected=bytearray(source)
    if mode!=2:
        if len(raw)>300:ref.RC4(raw).decrypt_into(expected,offset)
        else:ref.map_decrypt(expected,raw,offset)
    vectors.append((struct.pack('<IIIIQ',mode,len(encoded),len(raw),count,offset)+encoded+raw+source+bytes(expected),label))

for size in (16,64,300,301,512,1024,2048):
    raw=bytes((i*37+19)%256 for i in range(size))
    for offset in (0,1,127,128,5119,5120,5121,32767,32768,65535):add(0,raw,raw,offset,8193,'raw/random-access')
    add(0,raw,raw,268435456-1000,1000,'range-end')
    for version in ('raw','v1','v2'):
        encoded=base64.b64encode(raw) if version=='raw' else wrapped(raw,version=='v2')
        assert ref.derive_key(encoded)==raw
        add(1,encoded,raw,0,16385,'derive-'+version)
    add(1,wrapped(raw,False).rstrip(b'='),raw,5119,5121,'unpadded-v1')
add(0,b'\0'*512,b'\0'*512,127,8193,'zero-seed')
for size in range(16,24):
    raw=bytes((i*19+31)%256 for i in range(size))
    for version in (False,True):add(1,wrapped(raw,version),raw,0,1024,'all-tea-padding-lengths')
for size,offset in ((64,32767),(512,5119)):
    raw=bytes((i*37+19)%256 for i in range(size));add(0,raw,raw,offset,65536,'maximum-chunk')
for invalid in (b'',b'!',b'A',b'AB==',b'A===',base64.b64encode(b'short'),base64.b64encode(ref.V2P+b'broken')):
    add(2,invalid,b'',0,0,'invalid-key')
fixture=work/'synthetic.bin';fixture.write_bytes(struct.pack('<I',len(vectors))+b''.join(v[0] for v in vectors))
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
core=['runtime/apps/qqmusic/qqmusic_qmc.c','runtime/apps/qqmusic/qqmusic_protocol.c','runtime/apps/qqmusic/qqmusic_session.c','tools/fixtures/qqmusic_qmc.c']
sources=core+['runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'qmc-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),str(fixture)],cwd=ROOT,check=True,timeout=30)
host=work/'qmc-tests.sanitized'
subprocess.run(['gcc','-std=c99','-g','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host),str(fixture)],cwd=ROOT,check=True,timeout=30)
report={'passed':True,'synthetic_cases':len(vectors),'footer_bound_checks':4,'real_account_tested':False,'real_audio_tested':False,'device_tested':False,'objective_complete':False,
        'cases':sorted(set(label for _,label in vectors)),
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/qqmusic/qqmusic_qmc.h','third_party/qmc-reference/qmc2_reference.py','tools/test_qqmusic_qmc.py']},
        'limits':['Python reference agreement on synthetic keys/data is not real MGG or account qualification.',
                  'musicex footer length bounds only, no footer key parser, file conversion or codec/publication.','No secret key/plaintext logging; test key material stays in ignored work/.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
