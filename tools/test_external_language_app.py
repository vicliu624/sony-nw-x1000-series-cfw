"""Actual ARM Language app: dynamic packs, ID persistence and virtual UI only."""
from pathlib import Path
import subprocess,tempfile,shutil,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from language_pack import manifest
w=ROOT/'work/external-language-app-tests';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';app=ROOT/'work/external-language-app-build/HOMEBREW/apps/language/app';build=json.loads((ROOT/'work/external-language-app-build/build.json').read_text());assert hashlib.sha256(app.read_bytes()).hexdigest()==build['sha256'];body=(ROOT/'dist/0.1.0-dev.16/language-packs/en/HOMEBREW/languages/en/wording.stx').read_bytes()
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fPIC'];libdl=ROOT/'work/home-key-child-test/sysroot/lib/libdl.so.2'
source=ROOT/'work/language-app-tests/storage-preload.c';shutil.copyfile(source,w/'storage-preload.c');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-shared','-nostdlib','-Wl,--hash-style=sysv',str(w/'storage-preload.c'),str(lib/'libc.so.6'),str(libdl),'-lgcc','-o',str(w/'storage-preload.so')],check=True)
s=(ROOT/'tools/fixtures/device_preload.c').read_text().replace('#include "../../runtime/native/font.inc"','#include "'+str(ROOT/'runtime/native/font.inc')+'"');old='y=child()?(store_target()?400:100):(store_target()?60:120);';assert old in s;s=s.replace(old,'y=86+52*(unsigned)atoi(getenv("HB_LANG_ROW")?getenv("HB_LANG_ROW"):"0");');
s=s.replace('static int max_events(void){','static int max_events(void){if(getenv("HB_LANG_SWIPE"))return 8;')
needle='case 0x80045401:{assert(event<max_events());'
replacement='case 0x80045401:{assert(event<max_events());if(getenv("HB_LANG_SWIPE")){static const unsigned y[]={250,200,150,150,86,86,400,400},down[]={1,1,1,0,1,0,1,0};unsigned x=event<6?80:30,rx=(x*2929+239)/240,ry=((431-y[event])*5281+431)/432;unsigned char*b=argument;memset(b,0,16);b[1]=down[event];b[2]=rx>>8;b[3]=rx;b[4]=ry>>8;b[5]=ry;event++;break;}'
assert needle in s;s=s.replace(needle,replacement);(w/'virtual-devices.c').write_text(s);objects=[]
for i,path in enumerate([w/'virtual-devices.c',ROOT/'runtime/native/syscalls.S']):
 obj=w/(str(i)+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-D_GNU_SOURCE','-c',str(path),'-o',str(obj)],check=True);objects.append(str(obj))
subprocess.run(['arm-linux-gnueabi-gcc','-shared','-nostdlib','-Wl,--hash-style=sysv',*objects,str(lib/'libc.so.6'),'-lgcc','-o',str(w/'virtual-devices.so')],check=True)
prefix=w/'sysroot';(prefix/'lib').mkdir(parents=True,exist_ok=True)
for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
shutil.copyfile(libdl,prefix/'lib/libdl.so.2');storage=Path(tempfile.mkdtemp(prefix='storage-',dir=w));(storage/'contents/HOMEBREW/languages').mkdir(parents=True);(storage/'mounts').write_text('/dev/mtdblock/2 /contents vfat rw 0 0\n')
def install(ident,base,name,data):
 p=storage/'contents/HOMEBREW/languages'/ident;p.mkdir();(p/'language.ini').write_bytes(manifest(ident,name,base,data))
 if data is not None:(p/'wording.stx').write_bytes(data)
install('en','en','English',body);install('jp','jp','Japanese',None)
pref=storage/'contents/HOMEBREW/data/language/ui-language';rows=[]
def run(row,case,args=(),swipe=False):
 frame=w/(case+'.rgb565');cmd=['qemu-arm','-cpu','arm926','-L',str(prefix),'-E','LD_PRELOAD='+str(w/'storage-preload.so')+':'+str(w/'virtual-devices.so'),'-E','HB_TEST_MODE=loop','-E','HB_LANG_ROW='+str(row),'-E','HB_LANGUAGE_TEST_ROOT='+str(storage),'-E','HB_TEST_FRAME='+str(frame),*(['-E','HB_LANG_SWIPE=1']if swipe else[]),str(app),*args];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(w/(case+'.log')).write_text(r.stderr);assert r.returncode==0,(case,r.returncode,r.stderr[-3000:]);return r
r=run(0,'catalog',('--catalog',));assert r.stdout.splitlines()==['en\ten\tEnglish','jp\tjp\tJapanese'],r.stdout
for row,ident in [(0,'en'),(1,'jp'),(2,'stock')]:
 r=run(row,ident);assert pref.read_bytes()==(ident+'\n').encode(),(ident,pref.read_bytes(),r.stderr);assert 'VDEV RELEASE COMPLETE' in r.stderr and r.stderr.count('VDEV FRAME')==2;rows.append({'case':ident,'saved':pref.read_text(),'display_released':True})
# Add both Chinese packs to the same unchanged app binary.
for ident,base,name in [('zh-CN','cs','Simplified Chinese'),('zh-TW','ct','Traditional Chinese')]:
 source=ROOT/'dist/0.1.0-dev.16/language-packs'/ident/'HOMEBREW/languages'/ident/'wording.stx';install(ident,base,name,source.read_bytes())
for row,ident in [(2,'zh-CN'),(3,'zh-TW'),(4,'stock')]:
 run(row,ident);assert pref.read_bytes()==(ident+'\n').encode();rows.append({'case':ident,'saved':pref.read_text(),'display_released':True})
# Install a new ID without changing app or firmware; original metadata drives it.
install('demo-fr','fr','Test only',body);r=run(0,'catalog-added',('--catalog',));assert 'demo-fr\tfr\tTest only' in r.stdout;run(0,'custom-pack');assert pref.read_bytes()==b'demo-fr\n';rows.append({'case':'new-directory-discovered-without-rebuild','saved':'demo-fr','base':'fr','test_translation_only':True})
run(0,'second-page-original',swipe=True);assert pref.read_bytes()==b'stock\n';rows.append({'case':'swipe-to-second-page-select-original','saved':'stock'})
# Bad package is skipped and its ID is not selectable.
bad=storage/'contents/HOMEBREW/languages/broken';bad.mkdir();(bad/'language.ini').write_bytes(b'api=1\n');r=run(0,'catalog-invalid',('--catalog',));assert not any(line.startswith('broken\t')for line in r.stdout.splitlines())
# Removing a pack changes the discovered catalog without touching app bytes.
shutil.rmtree(storage/'contents/HOMEBREW/languages/demo-fr');r=run(0,'catalog-removed',('--catalog',));assert 'demo-fr'not in r.stdout;rows.append({'case':'removed-directory-no-longer-listed'})
before=pref.read_bytes();(storage/'mounts').write_text('/dev/root /contents ext2 rw 0 0\n');run(0,'wrong-mount');assert pref.read_bytes()==before;rows.append({'case':'wrong-mount-cannot-change-preference'})
assert hashlib.sha256(app.read_bytes()).hexdigest()==build['sha256']
report={'passed':True,'actual_app_sha256':build['sha256'],'cases':rows,'source_hashes':{str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'hardware_tested':False,'scope':'Actual ARM app and Sony libc; real PC files, virtual mount/device identity and display. Demo language uses test data, not a published French translation.'};(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
