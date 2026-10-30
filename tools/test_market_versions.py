"""SemVer, installed-state, confirmation and locked install-identity tests."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile
from market_metadata import compare_versions,check_history,descriptions,catalog_records
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
work=ROOT/'work/market-version-tests';work.mkdir(exist_ok=True)
sources=['tools/test_market_versions.c','runtime/store/canvas.c','runtime/native/frontend.c']+['runtime/store/'+x+'.c' for x in ('bundle_posix','package','inventory','cleanup_plan','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]+['runtime/native/sha256.c']
common=['-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
host=work/'host';subprocess.run(['gcc',*common,'-fsanitize=address,undefined','-fno-omit-frame-pointer',*sources,'-o',str(host)],check=True)
lib=ROOT/'work/arm-signal-tests/lib'
sdk=ROOT/'work/stock-resolver-probe'
arm=work/'arm';subprocess.run(['arm-linux-gnueabi-gcc',*common,'-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','tools/stock_test_start.c','tools/store_link_start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],check=True)
commands=[[str(host)],['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)]]
env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
for command in commands:subprocess.run(command,check=True,env=env)
assert compare_versions('1.10.0','1.9.0')==1 and compare_versions('1.0.0-alpha.10','1.0.0-alpha.2')==1
info=descriptions()
# Source discovery and intentional publication are separate contracts. New SDK
# examples (or third-party apps) must not require a global metadata ID list.
definitions={p.parent.name:json.loads(p.read_text()) for p in (ROOT/'runtime/apps').glob('*/app.json')}
assert set(info)==set(definitions)
published=set(json.loads((ROOT/'config/release.json').read_text())['apps'])
assert published<=set(info) and not published&{'pet','qqcheck'}
for ident,local in definitions.items():
    assert info[ident]=={field:local[field] for field in ('title','summary','description','changes','channel')}
assert info['pet']['title']=='BSOD Pet' and info['pet']['channel']=='experimental'
for old,new,oldhash,newhash,ok in [('1.0.0','1.1.0','a','b',True),('1.1.0','1.0.0','a','b',False),('1.0.0','1.0.0','a','a',True),('1.0.0','1.0.0+rebuild','a','b',False)]:
    try:check_history({'hello':{'version':new,'inventory_sha256':newhash}},[{'hello':{'version':old,'inventory_sha256':oldhash}}]);assert ok
    except ValueError:assert not ok
def package(folder,version,extra=b'original'):
    folder.mkdir(parents=True);app=(ROOT/'work/hello-app/package/app').read_bytes()
    data={'app':app,'app.ini':f'api=1\nid=hello\nname=Hello\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(app)}\nsha256={hashlib.sha256(app).hexdigest()}\n'.encode(),'resource.txt':extra}
    for name,value in data.items():(folder/name).write_bytes(value)
    (folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(v).hexdigest()} {len(v)} {n}\n' for n,v in sorted(data.items())))
scenarios=[('new',None,'1.0.0',0,'inspect'),('same','1.0.0','1.0.0',1,'inspect'),('update','1.9.0','1.10.0',2,'install'),('older','2.0.0','1.0.0',3,'inspect'),('repack','1.0.0','1.0.0',4,'inspect'),('corrupt','1.0.0','1.1.0',5,'inspect'),('legacy','old-build','1.0.0',6,'inspect'),('stale','1.0.0','1.1.0',2,'stale'),('appeared','1.0.0','1.1.0',2,'appeared'),('pending','1.0.0','1.1.0',5,'inspect'),('fresh',None,'1.0.0',0,'install')]
for command in commands:
    for name,installed,available,status,action in scenarios:
        with tempfile.TemporaryDirectory(prefix='case-',dir=work) as temp:
            root=Path(temp);incoming=root/'incoming';apps=root/'apps';apps.mkdir();(apps/'keep').write_bytes(b'KEEP')
            package(incoming,available)
            if installed:package(apps/'hello',installed,b'changed' if name=='repack' else b'original')
            if name=='corrupt':(apps/'hello/resource.txt').write_bytes(b'CORRUPT')
            if name=='pending':(apps/'.pending-hello').write_bytes(b'UNKNOWN TRANSACTION - KEEP')
            before={p.relative_to(apps).as_posix():p.read_bytes() for p in apps.rglob('*') if p.is_file()}
            subprocess.run(command+[str(incoming),str(apps),str(status),action],check=True,env=env,stdout=subprocess.DEVNULL,timeout=20)
            assert (apps/'keep').read_bytes()==b'KEEP'
            if action!='install':assert before=={p.relative_to(apps).as_posix():p.read_bytes() for p in apps.rglob('*') if p.is_file() and p.name!='.store-lock'}
            else:assert (apps/'hello/app.ini').read_bytes()==(incoming/'app.ini').read_bytes()
(work/'report.json').write_text(json.dumps({'passed':True,'host_sanitizers':True,'original_libc_arm':True,'state_scenarios':len(scenarios),'release_history_policy':True,'physical_device_accessed':False},indent=2)+'\n')
print('Market versions, details, immutable releases and guarded installs passed')
