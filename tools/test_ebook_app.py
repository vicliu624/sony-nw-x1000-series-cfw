"""Host/ARM reader tests, bounded writer fault fixtures and native virtual UI. No player access."""
from pathlib import Path
import subprocess,json,hashlib,tempfile,os,shutil
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/ebook-tests';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';rows=[]
subprocess.run([__import__('sys').executable,'tools/prepare_ebook_fixtures.py'],cwd=ROOT,check=True)
flags=['-std=c99','-O2','-DMINIZ_NO_STDIO','-DMINIZ_NO_TIME','-DMINIZ_NO_ARCHIVE_APIS','-DMINIZ_NO_DEFLATE_APIS','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-stack-protector','-ffunction-sections','-fdata-sections']
common=['tools/test_ebook.c','runtime/apps/ebook/reader.c','runtime/apps/ebook/storage.c','runtime/apps/ebook/ui.c','runtime/apps/dictionary/dictionary.c','runtime/native/sha256.c','runtime/apps/emulators/platform.c']
epub_sources=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'runtime/apps/ebook/epub').glob('*.c'))]+['third_party/epub-miniz/miniz_tinfl.c']
common+=epub_sources
for arm in [False,True]:
 out=w/('core-arm'if arm else'core-host');cmd=['arm-linux-gnueabi-gcc'if arm else'gcc',*flags,*common]
 if arm:cmd+=['-march=armv5te','-marm','-mfloat-abi=soft','-D_FILE_OFFSET_BITS=64','-nostdlib','-no-pie','-Wl,--hash-style=sysv','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
 else:cmd+=['tools/fixtures/ebook_host_stat.c']
 run=subprocess.run(cmd+['-Wl,--gc-sections','-o',str(out)],cwd=ROOT,capture_output=True,text=True);assert run.returncode==0,run.stderr
 run=subprocess.run((['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]if arm else[])+[str(out)],cwd=ROOT,capture_output=True,text=True,timeout=60);assert run.returncode==0,(arm,run.stdout,run.stderr);rows.append({'case':'core-arm'if arm else'core-host','exit':run.returncode,'stdout':run.stdout})
cmd=['gcc',*flags,'tools/test_ebook_storage.c','runtime/apps/ebook/storage.c','-Wl,--gc-sections','-o',str(w/'storage-host')]+['-Wl,--wrap='+n for n in ['open','fopen','mkdir','unlink','rename','fsync','write','realpath','statfs']]
run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);assert run.returncode==0,run.stderr
with tempfile.TemporaryDirectory(dir=w)as temp:
 run=subprocess.run([str(w/'storage-host')],cwd=ROOT,env={**os.environ,'ER_FIXTURE_ROOT':str(Path(temp).resolve())},capture_output=True,text=True,timeout=20);assert run.returncode==0,(run.stdout,run.stderr);rows.append({'case':'host-storage-faults-fixture','exit':run.returncode,'stdout':run.stdout})
# Production ARM binary: real assets, unverified user volume refused, virtual touch APPS exits.
src=(ROOT/'tools/fixtures/device_preload.c').read_text().replace('../../runtime/native/font.inc',str(ROOT/'runtime/native/font.inc')).replace('unsigned x=30,y=400','unsigned x=210,y=12');(w/'devices.c').write_text(src)
run=subprocess.run(['arm-linux-gnueabi-gcc','-D_GNU_SOURCE','-D_DEFAULT_SOURCE','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-fno-builtin','-shared','-nostdlib','-Wl,--hash-style=sysv',str(w/'devices.c'),'runtime/native/syscalls.S',str(lib/'libc.so.6'),'-lgcc','-o',str(w/'devices.so')],cwd=ROOT,capture_output=True,text=True);assert run.returncode==0,run.stderr
prefix=w/'sysroot';(prefix/'lib').mkdir(parents=True,exist_ok=True)
for n in ['libc.so.6','ld-linux.so.3']:shutil.copyfile(lib/n,prefix/'lib'/n)
assets=prefix/'contents/HOMEBREW/apps/ebook/assets';assets.mkdir(parents=True,exist_ok=True)
for n in ['font.bin','gb18030.bin']:
 dest=assets/n
 if not dest.exists():os.link(ROOT/'work/ebook-app/package/assets'/n,dest)
app=ROOT/'work/ebook-app/package/app';frame=w/'native-shelf.rgb565';run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-E','LD_PRELOAD='+str(w/'devices.so'),'-E','HB_TEST_FRAME='+str(frame),str(app)],cwd=ROOT,capture_output=True,text=True,timeout=30);assert run.returncode==0,(run.returncode,run.stdout,run.stderr);assert 'VDEV RELEASE COMPLETE'in run.stderr;rows.append({'case':'production-real-assets-unverified-volume-reject-and-touch-return','exit':run.returncode,'events':run.stderr.splitlines(),'sha256':hashlib.sha256(app.read_bytes()).hexdigest()})
report={'passed':True,'cases':rows,'hardware_tested':False,'device_written':False,'scope':'Host and ARM/QEMU real reader/encoding/UI tests. Persistence fault tests use normal PC files with wrapped logical paths and simulated VFAT metadata. No real VFAT/power-loss, real touch or USB qualification.'};(w/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
