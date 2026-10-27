"""Shared pack core tested with real files on host and ARM/Sony libc; PC only."""
from pathlib import Path
import subprocess,tempfile,shutil,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from language_pack import manifest,parse_manifest
w=ROOT/'work/external-language-pack-tests';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';data=(ROOT/'dist/0.1.0-dev.16/language-packs/en/HOMEBREW/languages/en/wording.stx').read_bytes()
def fixture():
 root=Path(tempfile.mkdtemp(prefix='files-',dir=w))
 for ident,name,base,body in [('en','English','en',data),('jp','Japanese','jp',None),('demo-fr','Test only','fr',data)]:
  folder=root/'HOMEBREW/languages'/ident;folder.mkdir(parents=True);m=manifest(ident,name,base,body);parse_manifest(m,body);(folder/'language.ini').write_bytes(m)
  if body is not None:(folder/'wording.stx').write_bytes(body)
 (root/'HOMEBREW/data/language').mkdir(parents=True);return root
sources=['tools/test_external_language_pack.c','runtime/apps/language/package.c','runtime/native/sha256.c'];flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-stack-protector','-fno-builtin'];rows=[]
for mode in ['host','arm']:
 out=w/('test-'+mode)
 if mode=='host':cmd=['gcc',*flags,*sources,'-o',str(out)];run=[str(out)]
 else:cmd=['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(out)];run=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(out)]
 subprocess.run(cmd,cwd=ROOT,check=True);root=fixture();r=subprocess.run(run+[str(root)],capture_output=True,text=True,timeout=30);assert r.returncode==0,(mode,r.returncode,r.stdout,r.stderr);rows.append({'mode':mode,'exit':r.returncode,'stdout':r.stdout})
report={'passed':True,'cases':rows,'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest()for s in sources+['runtime/apps/language/package.h','assets/language/required-ids.inc','assets/language/required-ids.json','assets/language/parameter-counts.inc','assets/language/parameter-counts.json','tools/test_external_language_pack.py']},'hardware_tested':False,'scope':'Parser, hash, bounded STX validation and file/heap cleanup; no Sony GUI integration'};(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
