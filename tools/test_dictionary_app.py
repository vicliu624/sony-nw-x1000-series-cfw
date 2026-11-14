"""Dictionary offline UI/core tests and actual ARM startup/return on virtual devices."""
import argparse
from pathlib import Path
import subprocess,json,shutil,os,hashlib,tempfile
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/dictionary-tests';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';rows=[]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package',type=Path,default=ROOT/'work/dictionary-app/package')
package=parser.parse_args().package.resolve()
if not package.is_relative_to((ROOT/'work').resolve()) or not (package/'app').is_file():
 parser.error('Select a built Dictionary package under work/')
flags=['-std=c99','-O2','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-stack-protector','-ffunction-sections','-fdata-sections']
common=['tools/test_dictionary.c','runtime/platform/text/lexicon.c','runtime/platform/text/bitmap_font.c','runtime/apps/dictionary/input.c','runtime/apps/dictionary/ui.c','runtime/apps/emulators/platform.c']
for arm in [False,True]:
 app=w/('core-arm'if arm else'core-host');cmd=['arm-linux-gnueabi-gcc'if arm else'gcc',*flags,*common]
 if arm:cmd+=['-march=armv5te','-marm','-mfloat-abi=soft','-D_FILE_OFFSET_BITS=64','-nostdlib','-no-pie','-Wl,--hash-style=sysv','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
 else:cmd+=['tools/fixtures/dictionary_host_stat.c']
 r=subprocess.run(cmd+['-Wl,--gc-sections','-o',str(app)],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
 run=subprocess.run((['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]if arm else[])+[str(app)],cwd=ROOT,capture_output=True,text=True,timeout=60);assert run.returncode==0,(arm,run.stdout,run.stderr);rows.append({'case':'core-arm'if arm else'core-host','stdout':run.stdout,'exit':run.returncode})
# Actual production binary and actual assets; only display/touch are interposed.
reference=w/'host-reference';reference.mkdir(exist_ok=True)
render=w/'host-render'
subprocess.run(['gcc',*flags,'tools/render_dictionary.c',*common[1:],'tools/fixtures/dictionary_host_stat.c','-Wl,--gc-sections','-o',str(render)],cwd=ROOT,check=True)
subprocess.run([str(render),str(package/'assets/lexicon.dic'),str(package/'assets/font.bin')],cwd=ROOT,env={**os.environ,'HB_DICT_RENDER_OUT':str(reference)},check=True)
src=(ROOT/'tools/fixtures/device_preload.c').read_text().replace('../../runtime/native/font.inc',str(ROOT/'runtime/native/font.inc')).replace('unsigned x=30,y=400','unsigned x=210,y=12');(w/'devices.c').write_text(src)
r=subprocess.run(['arm-linux-gnueabi-gcc','-D_GNU_SOURCE','-D_DEFAULT_SOURCE','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-fno-builtin','-shared','-nostdlib','-Wl,--hash-style=sysv',str(w/'devices.c'),'runtime/native/syscalls.S',str(lib/'libc.so.6'),'-lgcc','-o',str(w/'devices.so')],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,r.stderr
app=package/'app';frame=w/'production-home.rgb565'
with tempfile.TemporaryDirectory(prefix='sysroot-',dir=w) as temp:
 prefix=Path(temp);(prefix/'lib').mkdir()
 for n in ['libc.so.6','ld-linux.so.3']:shutil.copyfile(lib/n,prefix/'lib'/n)
 assets=prefix/'contents/HOMEBREW/apps/dictionary/assets';assets.mkdir(parents=True)
 for n in ['lexicon.dic','font.bin']:shutil.copyfile(package/'assets'/n,assets/n)
 r=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-E','LD_PRELOAD='+str(w/'devices.so'),'-E','HB_TEST_FRAME='+str(frame),str(app)],cwd=ROOT,capture_output=True,text=True,timeout=30)
assert r.returncode==0,(r.returncode,r.stdout,r.stderr)
assert 'VDEV RELEASE COMPLETE'in r.stderr
assert frame.read_bytes()==(reference/'01-home.rgb565').read_bytes(),'production/host home differ'
rows.append({'case':'production-real-assets-render-and-touch-return','exit':r.returncode,'events':r.stderr.splitlines(),'sha256':hashlib.sha256(app.read_bytes()).hexdigest()})
report={'passed':True,'cases':rows,'hardware_tested':False,'device_writes':False,'scope':'Actual full ECDICT, Unicode font and ARM binary on QEMU; display/touch virtual. No real player execution.'};(w/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
