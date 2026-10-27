"""Inactive package assembly and existing installer, host and Sony-libc QEMU."""
from pathlib import Path
import runpy, subprocess, tempfile, os, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/package-assemble-tests';work.mkdir(exist_ok=True)
files=metadata['files']; paths=sorted(p for p in files if p!='app.ini')
def array(name,data):
 return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in (data or b'\0'))+'};\n'
header=array('PLAN_MF',metadata['manifest'])+array('PLAN_IX',metadata['index'])
for i,p in enumerate(paths):header+=array('PLAN_BODY_'+str(i),files[p])
header+='static const unsigned char *PLAN_BODIES[]={'+','.join('PLAN_BODY_'+str(i) for i in range(len(paths)))+'};\n'
header+='static const unsigned PLAN_SIZES[]={'+','.join(str(len(files[p])) for p in paths)+'};\n'
header+='static const char *PLAN_PATHS[]={'+','.join(json.dumps(p) for p in paths)+'};\n'
(work/'package_task_fixture.h').write_text(header)
sources=['runtime/store/'+p+'.c' for p in ('package_assemble','download_plan','download_file','download_stream','https_url','bundle_posix','inventory','package','cleanup_plan','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]+['runtime/native/sha256.c','tools/test_package_assemble.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
runtime=metadata['work']
bridge=['runtime/store/'+p+'.c' for p in ('stock_fs_bridge','stock_stat64','stock_tls_compat')]+['tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode,discard in [(m,d) for m in ('complete','duplicate','exists','missing','corrupt','extra','link','oversize') for d in (False,True)]:
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';cache=base/'cache';apps=base/'apps'
   for p in (parent,cache,apps):p.mkdir()
   (apps/'unrelated.txt').write_bytes(b'KEEP');bundle=parent/'.bundle-demo'
   if mode=='exists':bundle.mkdir();(bundle/'keep').write_bytes(b'KEEP')
   run=subprocess.run(command,capture_output=True,text=True,timeout=20,env=dict(os.environ,**({'HB_ASM_DISCARD':'1'} if discard else {}),HB_ASM_CASE=mode,HB_ASM_PARENT=str(parent),HB_ASM_CACHE=str(cache),HB_ASM_APPS=str(apps)))
   assert run.returncode==0,(platform,mode,run.returncode,run.stderr)
   actual={str(p.relative_to(bundle)):p.read_bytes() for p in bundle.rglob('*') if p.is_file() and not p.is_symlink()}
   expected=dict(files,**{'files.sha256':metadata['index']})
   if mode=='exists':expected={'keep':b'KEEP'}
   elif mode=='missing':expected={p:expected[p] for p in ('app.ini','files.sha256')}
   elif mode=='corrupt':expected={p:expected[p] for p in ('app.ini','files.sha256','app')};expected['app']=bytes([files['app'][0]^1])+files['app'][1:]
   elif mode=='extra':expected['unknown']=b'KEEP'
   elif mode=='link':
    expected.pop('app');assert (bundle/'app').is_symlink() and os.readlink(bundle/'app')=='../outside'
   elif mode=='oversize':expected['app']+=b'X'
   if discard and mode not in ('exists','extra','link','oversize'):expected={};assert not bundle.exists()
   assert actual==expected,(platform,mode,actual.keys())
   assert not list(cache.iterdir()) and (apps/'unrelated.txt').read_bytes()==b'KEEP'
   if mode in ('complete','duplicate'):
    installed={str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file() and not p.is_symlink()}
    assert installed==dict(files,**{'files.sha256':metadata['index']})
    assert {p.name for p in apps.iterdir()} <= {'demo','unrelated.txt','.store-lock'}
   else:assert {p.name for p in apps.iterdir()}=={'unrelated.txt'}
   rows.append({'platform':platform,'case':mode,'explicit_discard':discard,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge},'limits':['Synthetic ARM ELF copied and installed, never executed.','Local temporary filesystem, not Sony FAT or power-loss qualification.','No networking in this assembly test; cache populated directly.','Same-process explicit discard tested; no restart adoption or automatic recovery.','Immutable plan and quiescent caller-owned directories required.','Not integrated into the device app-store candidate.']}
(ROOT/'sources/native-package-assemble-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Package assembly/install:',len(rows),'host/ARM cases passed.')
