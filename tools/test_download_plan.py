"""Metadata snapshots and per-file URL/key plan, host plus stock-libc ARM."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile,struct
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/download-plan-tests';work.mkdir(exist_ok=True)
program=bytearray(84);program[:7]=b'\x7fELF\x01\x01\x01';struct.pack_into('<HH',program,16,2,40);program=bytes(program)
base='https://example.test/apps/demo/0.1.0/'
def fixture(version):
 manifest=f'api=1\nid=demo\nname=Demo\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(program)}\nsha256={hashlib.sha256(program).hexdigest()}\n'.encode()
 files={'app':program,'app.ini':manifest,'assets/icon.bin':b'\0\xfficon','empty.dat':b''}
 index=b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {path}\n'.encode() for path,data in sorted(files.items()))
 identity=hashlib.sha256(b'HBPKG001'+hashlib.sha256(manifest).digest()+hashlib.sha256(program).digest()+b'\x01'+struct.pack('<I',len(index))+hashlib.sha256(index).digest()).digest()
 return manifest,index,identity,files
manifest,index,identity,files=fixture('0.1.0');manifest2,index2,_,_=fixture('0.1.1')
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
paths=[p for p in sorted(files) if p!='app.ini'];keys=[hashlib.sha256(b'HBFILEKEY1'+identity+p.encode()).hexdigest()[:32] for p in paths]
header=array('MF',manifest)+array('IX',index)+array('MF2',manifest2)+array('IX2',index2)+array('IDENTITY',identity)
header+='static const char *BASE='+json.dumps(base)+';\n'
header+='static const char *PATHS[]={'+','.join(json.dumps(p) for p in paths)+'};\n'
header+='static const char *URLS[]={'+','.join(json.dumps(base+p) for p in paths)+'};\n'
header+='static const char *KEYS[]={'+','.join(json.dumps(k) for k in keys)+'};\n'
header+='static const unsigned SIZES[]={'+','.join(str(len(files[p])) for p in paths)+'};\n'
header+='static const unsigned char DIGESTS[][32]={'+','.join('{'+','.join(str(b) for b in hashlib.sha256(files[p]).digest())+'}' for p in paths)+'};\n'
(work/'plan_fixture.h').write_text(header)
sources=['runtime/store/download_plan.c','runtime/store/inventory.c','runtime/store/package.c','runtime/store/cleanup_plan.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/test_download_plan.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-I'+str(work),*sources,'-o',str(work/'host')],cwd=ROOT,check=True);subprocess.run([str(work/'host')],check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
(work/'ld-2.3.3.so').chmod(0o755)
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-I'+str(work),*sources,'runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/stock_test_start.c','tools/store_link_start.S',str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')],capture_output=True,text=True,timeout=15);assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'platforms':['host','ARM/QEMU original libc'],'checks':['manifest/index binding and known package identity','three network files include empty resource','independent Python SHA256-derived cache keys','deep-copy metadata survives caller changes','version change changes cache key','lookup error leaves output unchanged','base URL constraints and joined path cap','invalid manifest/index/id rejected'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'fixture_sha256':hashlib.sha256(header.encode()).hexdigest(),'limits':['Metadata planning only, not bootstrap trust verification or file downloading.','App/index metadata provided inline; app ELF/body validity deferred to complete bundle validation.','No package assembly, disk peak bound, publication or app activation.']}
(ROOT/'sources/native-download-plan-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Package download plan snapshots/keys passed on host and ARM/QEMU.')
