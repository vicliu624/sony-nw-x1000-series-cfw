"""Explicit public-release to actual ARM market install check; PC sandbox only."""
from pathlib import Path
import argparse,ast,hashlib,io,json,os,ssl,subprocess,tempfile,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',default='vicliu624/sony-nw-x1000-series-cfw');p.add_argument('--tag',required=True);a=p.parse_args()
base='https://github.com/'+a.repository+'/releases/download/'+a.tag+'/'
def fetch(name):
 with urllib.request.urlopen(base+name,timeout=45) as response:return response.read()
checksums=dict(line.split('  ',1)[::-1] for line in fetch('SHA256SUMS').decode().splitlines())
def verified(name):
 data=fetch(name)
 if hashlib.sha256(data).hexdigest()!=checksums[name]:raise ValueError('Published hash mismatch: '+name)
 return data
manifest=json.loads(verified('release-manifest.json'));setup=verified('market-source.zip');expected=next(x['sha256'] for x in manifest['apps'] if x['id']=='hello')
work=ROOT/'work/ci/published-market';work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';sdk=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
syntax=ast.parse((ROOT/'tools/build_network_store_app.py').read_text());modules=next(ast.literal_eval(n.value) for n in syntax.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='modules' for t in n.targets))
sources=['runtime/store/'+n+'.c' for n in modules if n not in ('network_main','network_app','platform_native','termination')]+['runtime/store/start.S','runtime/native/frontend.c','runtime/native/sha256.c','tools/release_market_probe.c']
app=work/'probe.arm';flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(sdk),'-I'+str(sdk),'-I'+str(crypto/'bearssl-0.6/inc')]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(crypto/'arm-build/libbearssl.a'),str(sdk/'libcares.so.2'),str(sdk/'librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='install-',dir=work) as temporary:
 root=Path(temporary)
 for name in ('repository','cache','packages','apps'):(root/name).mkdir()
 with zipfile.ZipFile(io.BytesIO(setup)) as z:
  assert set(z.namelist())=={'HOMEBREW/repository/ca.der','HOMEBREW/repository/repository.conf'}
  for name in ('ca.der','repository.conf'):(root/'repository'/name).write_bytes(z.read('HOMEBREW/repository/'+name))
 (root/'apps/unrelated').write_bytes(b'KEEP')
 env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
 result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(sdk),str(app),str(root)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=150)
 (work/'run.log').write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError((result.returncode,result.stdout,result.stderr))
 assert hashlib.sha256((root/'apps/hello/app').read_bytes()).hexdigest()==expected
 assert (root/'apps/unrelated').read_bytes()==b'KEEP'
 print(result.stdout)
report={'passed':True,'repository':a.repository,'tag':a.tag,'source_commit':manifest['source_commit'],'public_github_release_used':True,'actual_arm_market_list_select_download_and_install':True,'hello_sha256':expected,'os_verified_public_metadata':True,'native_tls_redirects_and_hashes':True,'unrelated_files_preserved':True,'physical_player_accessed':False}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
