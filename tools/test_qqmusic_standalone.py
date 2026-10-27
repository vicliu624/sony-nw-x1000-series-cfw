"""Build standalone and execute its real main with simulated bottom IO only."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
from pathlib import Path
import json,subprocess,tempfile,sys,shutil,hashlib,struct,zlib
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-standalone';work.mkdir(exist_ok=True)
directory=Path(tempfile.mkdtemp(prefix='synthetic-',dir=work))
subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(directory/'key.pem'),'-out',str(directory/'cert.pem'),'-days','1','-subj','/CN=synthetic-build-only','-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['openssl','x509','-in',str(directory/'cert.pem'),'-outform','DER','-out',str(directory/'ca.der')],check=True)
profile={'source':'/dev/mock-user','resources':'/contents/HOMEBREW/apps/qqmusic/resources','guid':'123456789','ca_files':['ca.der'],'comm':{'ct':'11','cv':'20090008','tmeLoginType':'2','QIMEI36':'synthetic-only','OpenUDID':'synthetic-only','udid':'synthetic-only','aid':'synthetic-only','phonetype':'fixture','os_ver':'fixture','chid':'10003505','tmeAppID':'qqmusic'}}
path=directory/'profile.json';path.write_text(json.dumps(profile))
subprocess.run([sys.executable,'tools/build_qqmusic_native.py','--profile',str(path),'--output',str(directory/'candidate')],cwd=ROOT,check=True)
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';math=ROOT/'work/qqmusic-codec/libm.so.6'
build=json.loads((directory/'candidate/build.json').read_text());sources=list(build['sources'])
sources.remove('runtime/apps/qqmusic/qqmusic_main.c');sources.remove('runtime/native/syscalls.S');sources.append('tools/fixtures/qqmusic_native_boot.c')
sources+=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in ('source','output','directory','stage','stage_volume')]
app=directory/'native-main-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64','-I'+str(resolver),'-I'+str(directory/'candidate'),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb',*sources,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
for fault in range(4):
 with tempfile.TemporaryDirectory(prefix='native-boot-',dir=directory) as temporary:
  shutil.copyfile(ROOT/'work/qqmusic-font/QQMusicUI.otf',Path(temporary)/'font.otf')
  result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app),temporary,str(fault)],cwd=ROOT,capture_output=True,text=True,timeout=30)
  assert result.returncode==0,(fault,result.returncode,result.stderr[-4000:])
  if fault==0:
   frame=Path(temporary)/'frame.rgb565';values=struct.unpack('<103680H',frame.read_bytes());frame.unlink();raw=bytearray()
   for y in range(432):
    raw.append(0)
    for value in values[y*240:(y+1)*240]:raw.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
   def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
   (directory/'native-first-frame.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
  assert not list(Path(temporary).iterdir())
profile['comm']['authst']='forbidden-synthetic';path.write_text(json.dumps(profile))
result=subprocess.run([sys.executable,'tools/build_qqmusic_native.py','--profile',str(path),'--output',str(directory/'rejected')],cwd=ROOT,capture_output=True,text=True)
assert result.returncode and not (directory/'rejected').exists()
(directory/'key.pem').unlink();path.unlink()
report={'passed':True,'scope':'standalone_build_cli_and_actual_main_simulated_native_boot','synthetic_profile':True,'physical_device_tested':False,'native_entry_simulated':True,'checks':['readonly help and version','actual main deployment-path entry','embedded CA decode','actual signal handler stop','real font and renderer','display failure cleanup','close failure propagation','signal installation failure prevents device open'],'account_fields_rejected_before_output':True,'candidate':str((directory/'candidate').relative_to(ROOT)),'fixture_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/fixtures/qqmusic_native_boot.c','tools/fixtures/qqmusic_entry_boot.c','tools/fixtures/qqmusic_volume.c']},'test_arm_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'limits':['Bottom hardware IO and mount/path mapping are fixtures.','No QQ service contacted or physical player execution.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
