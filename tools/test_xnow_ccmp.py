"""Independent PyCryptodome reference vs BearSSL C CCMP, host and stock ARM."""
from pathlib import Path
import hashlib,json,subprocess
from Crypto.Cipher import AES
from app_registry import ROOT
OUT=ROOT/'work/espnow-ccmp-tests';OUT.mkdir(exist_ok=True)
B=ROOT/'work/external-tls-probe/bearssl-0.6';hostlib=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a';armlib=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
key=bytes(range(16));header=bytes.fromhex('d028341202010203040502060708090affffffffffff3012')
assert len(header)==24
vectors=[]
for n in (0,15,16,17,265,1520):
 for pn in (1,0x010203040506):
  protected=header[:1]+bytes([header[1]|64])+header[2:]
  nonce=b'\x10'+header[10:16]+pn.to_bytes(6,'big')
  aad=bytes([header[0],(header[1]&0xc7)|64])+header[4:22]+bytes([header[22]&15,0])
  cipher=AES.new(key,AES.MODE_CCM,nonce=nonce,mac_len=8);cipher.update(aad)
  ciphertext,tag=cipher.encrypt_and_digest(bytes((i*17+3)&255 for i in range(n)))
  iv=pn.to_bytes(6,'little');ccmp=iv[:2]+b'\x00\x20'+iv[2:]
  vectors.append((n,pn,protected+ccmp+ciphertext+tag))
def arr(data):return ','.join(str(x) for x in data)
text='static const unsigned char key[16]={'+arr(key)+'};\nstatic const unsigned char header[24]={'+arr(header)+'};\n'
for i,(_,_,frame) in enumerate(vectors):text+='static const unsigned char frame'+str(i)+'[]={'+arr(frame)+'};\n'
text+='static const struct vector {unsigned bytes;uint64_t pn;const unsigned char *frame;} vectors[]={\n'
for i,(n,pn,_) in enumerate(vectors):text+='{'+str(n)+',UINT64_C('+str(pn)+'),frame'+str(i)+'},\n'
text+='};\n';(OUT/'ccmp_vectors.h').write_text(text)
sources=['tools/test_xnow_ccmp.c','runtime/platform/espnow/xnow_ccmp.c'];include=['-I',str(B/'inc'),'-I',str(OUT)]
host=OUT/'ccmp.host';subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*include,*sources,str(hostlib),'-o',str(host)],cwd=ROOT,check=True)
a=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=30)
lib=ROOT/'work/arm-signal-tests/lib';arm=OUT/'ccmp.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*include,*sources,'runtime/store/start.c','runtime/store/start.S',str(armlib),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
b=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,check=True,timeout=60)
report={'passed':True,'independent_reference':'PyCryptodome AES-CCM with explicit standard management AAD/nonce','vectors':len(vectors),'host_asan_ubsan':a.stdout,'arm926_stock_libc':b.stdout,'physical_espnow_encryption_verified':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_ccmp.h','tools/test_xnow_ccmp.py']},'vectors_sha256':hashlib.sha256((OUT/'ccmp_vectors.h').read_bytes()).hexdigest(),'bearssl_archives':{'host':hashlib.sha256(hostlib.read_bytes()).hexdigest(),'arm':hashlib.sha256(armlib.read_bytes()).hexdigest()}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
