"""Unchanged selected launcher -> unchanged graphics ELF -> launcher, virtual I/O and exec bridge."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import contextlib,hashlib,io,json,runpy,shutil,subprocess,tempfile,struct,zlib
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_libc_production_ui.py'))
work=work_area(ROOT,'libc-production-app-loop-review')
composition=base['composition'];app=base['app'];preload=base['preload'];lib=base['lib']
child=composition/'external/HOMEBREW/apps/graphics-demo/app';manifest=base['manifest']
for path in (app,child):
 row=next(r for r in manifest['files'] if r['path']==str(path.relative_to(composition)));assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
with tempfile.TemporaryDirectory(dir=work) as temporary:
 prefix=Path(temporary);(prefix/'lib').mkdir()
 for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
 shutil.copytree(composition/'external/HOMEBREW/apps',prefix/'contents/HOMEBREW/apps')
 environment={'LD_PRELOAD':str(preload),'HB_TEST_MODE':'loop','HB_TEST_PREFIX':str(prefix),'HB_TEST_PRELOAD':str(preload),'HB_TEST_FRAME':str(work/'launcher.rgb565'),'HB_TEST_CHILD_FRAME':str(work/'graphics.rgb565')}
 command=['qemu-arm','-cpu','arm926','-L',str(prefix),'-0','/contents/HOMEBREW/launcher/app']
 for key,value in environment.items():command+=['-E',key+'='+value]
 run=subprocess.run(command+[str(app),'--native'],cwd=ROOT,capture_output=True,text=True,timeout=20)
 assert run.returncode==0,(run.returncode,run.stdout,run.stderr)
 (work/'last-run.log').write_text(run.stderr)
 events=[s for s in run.stderr.splitlines() if s.startswith('VDEV ')]
 assert events.count('VDEV EXEC GRAPHICS')==1 and events.count('VDEV OPEN FB')==2 and events.count('VDEV RELEASE COMPLETE')==2,events
 assert events.count('VDEV CHILD OPEN FB')==1 and events.count('VDEV CHILD FRAME')==2 and events.count('VDEV CHILD RELEASE COMPLETE')==1,events
 assert events.index('VDEV RELEASE COMPLETE')<events.index('VDEV EXEC GRAPHICS')<events.index('VDEV CHILD OPEN FB')<events.index('VDEV CHILD RELEASE COMPLETE')<len(events)-1
 assert events[-1]=='VDEV RELEASE COMPLETE'
 assert not run.stdout and 'symbol lookup error' not in run.stderr
 for path in (app,child):
  expected=next(r['sha256'] for r in manifest['files'] if r['path']==str(path.relative_to(composition)))
  assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
assert int.from_bytes((work/'graphics.rgb565').read_bytes()[:2],'little')==0x0320
for name in ('launcher','graphics'):
 raw=(work/(name+'.rgb565')).read_bytes();assert len(raw)==240*432*2;rgb=bytearray()
 for offset in range(0,len(raw),2):
  value=int.from_bytes(raw[offset:offset+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
 (work/(name+'.png')).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
tracked=[Path(__file__),ROOT/'tools/test_libc_production_ui.py',ROOT/'tools/fixtures/device_preload.c',ROOT/'runtime/native/syscalls.S',app,child,preload,composition/'manifest.json',lib/'libc.so.6',lib/'ld-linux.so.3',*work.glob('*.png'),*work.glob('*.rgb565')]
report={'passed':True,'unchanged_launcher_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'unchanged_graphics_sha256':hashlib.sha256(child.read_bytes()).hexdigest(),'exit':run.returncode,'events':events,'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['Actual launcher/app bytes run; device I/O and chdir path mapping interposed; exec explicitly bridged through nested host QEMU.','Not actual Sony kernel, GUI/proxy, USB handoff or device rendering.','Preload library and bridge are test-only and absent from app packages.']}
write_report(ROOT,'native-libc-production-app-loop-tests.json',report);print('Actual selected ELF pair: launcher -> graphics tap/exit -> launcher return passed; virtual devices and explicit QEMU exec bridge.')



