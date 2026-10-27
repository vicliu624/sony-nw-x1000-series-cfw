"""Complete inactive bundle re-opened by a fresh process; no partial adoption."""
from pathlib import Path
import runpy,subprocess,tempfile,hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
metadata=runpy.run_path(str(ROOT/'tools/test_download_plan.py'))
work=ROOT/'work/package-resume-tests';work.mkdir(exist_ok=True)
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in data)+'};\n'
mf2,ix2,_,_=metadata['fixture']('0.1.1')
header=array('MF',metadata['manifest'])+array('IX',metadata['index'])+array('MF2',mf2)+array('IX2',ix2);(work/'resume_fixture.h').write_text(header)
sources=['runtime/store/'+p+'.c' for p in ('package_resume','package_assemble','download_plan','download_file','download_stream','https_url','bundle_posix','inventory','package','cleanup_plan','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]+['runtime/native/sha256.c','tools/test_package_resume.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(work)]
subprocess.run(['gcc',*common,*sources,'-o',str(work/'host')],cwd=ROOT,check=True)
runtime=metadata['work'];bridge=['runtime/store/'+p+'.c' for p in ('stock_fs_bridge','stock_stat64','stock_tls_compat')]+['tools/stock_test_start.c','tools/store_link_start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,str(runtime/'libc-2.3.3.so'),str(runtime/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
def tree(root):return {str(p.relative_to(root)):('link:'+os.readlink(p)) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory' for p in root.rglob('*')}
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(work/'arm')])]:
 for mode in ('complete','discard','install','absent','cancel','identity','missing','hash','extra','link','hardlink','root-link','parent-alias','unknown-dir'):
  with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
   base=Path(temp);parent=base/'packages';parent.mkdir();apps=base/'apps';apps.mkdir();(apps/'keep').write_bytes(b'KEEP');bundle=parent/'.bundle-demo';actual=parent
   files=dict(metadata['files'],**{'files.sha256':metadata['index']})
   if mode!='absent':
    for name,data in files.items():p=bundle/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   if mode=='missing':(bundle/'empty.dat').unlink()
   elif mode=='hash':(bundle/'app').write_bytes(b'X'*len(files['app']))
   elif mode=='extra':(bundle/'extra').write_bytes(b'KEEP')
   elif mode=='link':(bundle/'app').unlink();(base/'outside').write_bytes(files['app']);(bundle/'app').symlink_to(base/'outside')
   elif mode=='hardlink':os.link(bundle/'app',base/'outside')
   elif mode=='root-link':bundle.rename(base/'saved');bundle.symlink_to(base/'saved',target_is_directory=True)
   elif mode=='parent-alias':actual=base/'alias';actual.symlink_to(parent,target_is_directory=True)
   elif mode=='unknown-dir':(bundle/'unknown').mkdir()
   before=tree(base)
   run=subprocess.run(command,capture_output=True,text=True,timeout=15,env=dict(os.environ,HB_RESUME_MODE=mode,HB_RESUME_PACKAGES=str(actual),HB_RESUME_APPS=str(apps)))
   assert run.returncode==0,(platform,mode,run.returncode,run.stderr)
   if mode=='discard':assert not bundle.exists() and tree(apps)=={'keep':hashlib.sha256(b'KEEP').hexdigest()}
   elif mode=='install':assert {str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file()}==files
   else:assert tree(base)==before,(platform,mode)
   assert (apps/'keep').read_bytes()==b'KEEP';rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge},'limits':['Fresh process reads preexisting fixture; complete bundle only, no persisted partial intent or resume of partial downloads.','Quiescent temporary filesystem, not concurrent mutation or Sony FAT/power-loss qualification.','Synthetic ARM ELF never executed.']}
(ROOT/'sources/native-package-resume-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Complete bundle restart adoption:',len(rows),'host/ARM cases passed.')
