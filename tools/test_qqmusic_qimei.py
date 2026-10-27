"""ARM QIMEI protocol interoperability with synthetic installation data only."""
import base64,hashlib,hmac,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-qimei';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';bear=ROOT/'work/external-tls-probe'
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('qimei','json','protocol','session','http','cookie','response')]
core+=['runtime/store/'+n+'.c' for n in ('tls_platform','https_url','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]
core+=['runtime/store/start.S','runtime/native/sha256.c','tools/fixtures/qqmusic_qimei.c']
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
app=work/'qimei.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(bear/'bearssl-0.6/inc'),*core,str(bear/'arm-build/libbearssl.a'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)],capture_output=True,text=True,check=True,timeout=20)
lines=result.stdout.splitlines();assert len(lines)==2
params=json.loads(lines[0])['qimeiParams'];header_sign=lines[1]
# Independent SP800-90A HMAC-DRBG reference, including updates between calls.
K=bytes(32);V=bytes([1])*32
def mac(key,data):return hmac.digest(key,data,'sha256')
def update(seed=b''):
 global K,V
 K=mac(K,V+b'\0'+seed);V=mac(K,V)
 if seed:K=mac(K,V+b'\1'+seed);V=mac(K,V)
def generate(n):
 global V
 output=b''
 while len(output)<n:V=mac(K,V);output+=V
 update();return output[:n]
update(bytes(range(1,49)));entropy=generate(16);key=entropy[:8].hex().encode();nonce=entropy[8:].hex()
padding=b''
while len(padding)<109:
 value=generate(1)
 if value!=b'\0':padding+=value
modulus=int('c4231830a2eb5fc2827170641e79d80fec51bda9a22e4b4ab37d1f205a4ae44d928cda25879f66a3429051663312a127faf8a246bdaaf63918417e90d7c95b5908aa6a2d0f852e4a6770294a548ac1c2fe8f1f252fb826f4ac86ab9a00e7ce47d002a56e7c4b51eb889acc60ca6adbc9f72e81f4d31b1dd7464805264530ab1d',16)
expected=pow(int.from_bytes(b'\0\2'+padding+b'\0'+key,'big'),65537,modulus).to_bytes(128,'big')
assert base64.b64decode(params['key'],validate=True)==expected
plain=subprocess.run(['openssl','enc','-d','-aes-128-cbc','-K',key.hex(),'-iv',key.hex(),'-nopad'],input=base64.b64decode(params['params'],validate=True),capture_output=True,check=True).stdout
pad=plain[-1];assert 1<=pad<=16 and plain[-pad:]==bytes([pad])*pad
assert json.loads(plain[:-pad])=={'model':'NW-X1060','brand':'Sony','test':'synthetic-installation-only'}
assert params['nonce']==nonce and params['time']=='1700000000'
assert params['sign']==hashlib.md5((params['key']+params['params']+'1700000000000'+nonce+'ZdJqM15EeO2zWc08'+params['extra']).encode()).hexdigest()
assert header_sign==hashlib.md5(b'qimei_qq_androidpzAuCmaFAaFaHrdakPjLIEqKrGnSOOvH1700000000').hexdigest()
report={'passed':True,'scope':'ARM QIMEI request crypto and anonymous HTTP profile','synthetic_only':True,'service_contacted':False,'account_accessed':False,'device_accessed':False,'checks':['independent HMAC-DRBG/RSA PKCS1-v1.5 result','independent AES-CBC PKCS7 decrypt and payload equality','request and header MD5 compatibility','no account Cookie to QIMEI','fixed origin and timestamp checks','ignore response cookies','nested QIMEI response parse','incomplete TLS response refuses IDs','stopped request clears output'],'app_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core},'limits':['Synthetic payload is not a production fingerprint policy.','No real QIMEI initialization, login or device execution.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
