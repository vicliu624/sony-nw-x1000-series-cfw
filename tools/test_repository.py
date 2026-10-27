"""Read-only repository configuration and pinned DER CA, host/stock-libc ARM."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os,ssl
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
subprocess.run([os.sys.executable,str(ROOT/'tools/probe_external_tls.py')],cwd=ROOT,check=True)
work=ROOT/'work/repository-tests';work.mkdir(exist_ok=True)
crypto=ROOT/'work/external-tls-probe/bearssl-0.6';runtime=metadata['work']
rsa=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-rsa.pem').read_text());ec=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-ec.pem').read_text());leaf=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-ee-rsa.pem').read_text())
host_library=work/'bearssl-host/libbearssl.a'
build=subprocess.run(['make','-C',str(crypto),'-j4','lib','CC=gcc','AR=ar','CFLAGS=-O2','BUILD='+str(host_library.parent)],capture_output=True,text=True);assert build.returncode==0,build.stderr
sources=['runtime/store/repository.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/test_repository.c']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(crypto/'inc')]
subprocess.run(['gcc',*common,*sources,str(host_library),'-o',str(work/'host')],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def config(ca):return ('HBREPO1\ncatalog_url=https://example.test/catalog.txt\ncatalog_bytes=9\ncatalog_sha256='+hashlib.sha256(b'HBSTORE1\n').hexdigest()+'\nca_sha256='+hashlib.sha256(ca).hexdigest()+'\n').encode()
def snapshot(base):return {str(p.relative_to(base)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*') if p.is_file() or p.is_symlink()}
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('rsa','ec','missing-config','missing-ca','missing-root','hash','garbage','leaf','ca-link','config-link','dangling-config-link','ca-hardlink','root-alias','oversize-config','truncated-der','extra-der','no-newline','duplicate','unknown','crlf','nul','http','zero','large','missing-field','uppercase','cancel'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);folder=base/'repository';folder.mkdir();actual=folder;expected=0
   cert=ec if mode=='ec' else leaf if mode=='leaf' else b'garbage' if mode=='garbage' else rsa[:-1] if mode=='truncated-der' else rsa+b'X' if mode=='extra-der' else rsa
   text=config(cert);(folder/'ca.der').write_bytes(cert)
   if mode=='missing-root':actual=base/'missing-root';expected=-115
   elif mode=='missing-config':expected=-115
   elif mode=='missing-ca':(folder/'ca.der').unlink();expected=-115
   elif mode=='hash':(folder/'ca.der').write_bytes(cert+b'X');expected=-112
   elif mode in ('garbage','leaf','truncated-der','extra-der'):expected=-113
   elif mode=='ca-link':(folder/'ca.der').rename(base/'other');(folder/'ca.der').symlink_to(base/'other');expected=-111
   elif mode in ('config-link','dangling-config-link'):expected=-111
   elif mode=='ca-hardlink':os.link(folder/'ca.der',base/'other');expected=-111
   elif mode=='root-alias':actual=base/'alias';actual.symlink_to(folder,target_is_directory=True);expected=-111
   elif mode=='oversize-config':text=b'X'*4097;expected=-111
   elif mode=='no-newline':text=text[:-1];expected=-110
   elif mode=='duplicate':text+=b'catalog_bytes=9\n';expected=-110
   elif mode=='unknown':text+=b'extra=yes\n';expected=-110
   elif mode=='crlf':text=text.replace(b'\n',b'\r\n');expected=-110
   elif mode=='nul':text=text.replace(b'https',b'htt\0s');expected=-110
   elif mode=='http':text=text.replace(b'https:',b'http:');expected=-110
   elif mode=='zero':text=text.replace(b'catalog_bytes=9',b'catalog_bytes=0');expected=-110
   elif mode=='large':text=text.replace(b'catalog_bytes=9',b'catalog_bytes=32769');expected=-110
   elif mode=='missing-field':text=b'\n'.join(text.split(b'\n')[:-2])+b'\n';expected=-110
   elif mode=='uppercase':text=text.replace(hashlib.sha256(cert).hexdigest().encode(),hashlib.sha256(cert).hexdigest().upper().encode());expected=-110
   elif mode=='cancel':expected=-114
   if mode!='missing-config':(folder/'repository.conf').write_bytes(text)
   if mode=='config-link':(folder/'repository.conf').rename(base/'other');(folder/'repository.conf').symlink_to(base/'other')
   if mode=='dangling-config-link':(folder/'repository.conf').unlink();(folder/'repository.conf').symlink_to(base/'absent')
   before=snapshot(base)
   env=dict(os.environ,HB_REPO_ROOT=str(actual),HB_REPO_EXPECT=str(expected),**({'HB_REPO_EC':'1'} if mode=='ec' else {}),**({'HB_REPO_STOP':'1'} if mode=='cancel' else {}))
   run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=env);assert run.returncode==0,(platform,mode,run.returncode,run.stderr)
   assert before==snapshot(base),(platform,mode)
   rows.append({'platform':platform,'case':mode,'expected_result':expected,'passed':True})
report={'generator_source':'tools/test_repository.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge+['runtime/store/repository.h','runtime/store/https_url.h','runtime/native/sha256.h']},'limits':['Sample public test certificates only; no production trust decision or live TLS handshake in this loader test.','Canonical quiescent temporary directory; not filesystem confinement or concurrent mutation protection.','One fingerprint-matched CA DER, no PEM/bundle/system-root fallback.','No native app integration or hardware qualification.']}
(ROOT/'sources/native-repository-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Repository read-only config/DER:',len(rows),'host/ARM cases passed.')
