"""Actual unchanged r3 store: fetch HTTPS catalog with real TLS, virtual devices."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import contextlib,hashlib,io,json,runpy,shutil,subprocess,tempfile,re,struct,zlib
from local_store_https import repository_fixture
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_libc_production_ui.py'))
work=work_area(ROOT,'production-store-launcher-review')
composition=base['composition'];store=composition/'external/HOMEBREW/apps/store/app';preload=base['preload'];lib=base['lib']
expected=next(r['sha256'] for r in base['manifest']['files'] if r['path']=='external/HOMEBREW/apps/store/app');assert hashlib.sha256(store.read_bytes()).hexdigest()==expected
with repository_fixture(ROOT/'work/hello-app/package') as fixture:
 prefix=fixture['area']/'sysroot';(prefix/'lib').mkdir(parents=True)
 resolver=json.loads((ROOT/'sources/native-stock-resolver-probe.json').read_text())
 for name in ('libc.so.6','ld-linux.so.3','libcares.so.2','librt.so.1','libpthread.so.0'):
  original=ROOT/'work/stock-resolver-probe'/name;assert hashlib.sha256(original.read_bytes()).hexdigest()==resolver['libraries'][name]['sha256'];shutil.copyfile(original,prefix/'lib'/name)
 home=prefix/'contents/HOMEBREW';home.mkdir(parents=True)
 shutil.copytree(fixture['configuration'],home/'repository');(home/'cache').mkdir();(home/'packages').mkdir();(home/'apps').mkdir()
 before={p.name:p.read_bytes() for p in (home/'repository').iterdir()}
 shutil.copytree(composition/'external/HOMEBREW/apps/store',home/'apps/store')
 launcher=composition/'external/HOMEBREW/launcher/app'
 settings={'LD_PRELOAD':str(preload),'HB_TEST_MODE':'loop','HB_TEST_TARGET':'store','HB_TEST_NETWORK':'install','HB_TEST_TRACE_CHILD':'1','HB_TEST_PREFIX':str(prefix),'HB_TEST_PRELOAD':str(preload),'HB_TEST_CHILD_FRAME':str(work/'catalog.rgb565'),'HB_TEST_FRAME':str(work/'launcher.rgb565')}
 command=['qemu-arm','-strace','-cpu','arm926','-L',str(prefix),'-0','/contents/HOMEBREW/launcher/app']
 for key,value in settings.items():command+=['-E',key+'='+value]
 try:run=subprocess.run(command+[str(launcher),'--native'],cwd=ROOT,capture_output=True,text=True,timeout=35)
 except subprocess.TimeoutExpired as error:
  (work/'last-run.log').write_bytes(error.stderr or b'');raise
 (work/'last-run.log').write_text(run.stderr)
 assert run.returncode==0,(run.returncode,run.stderr[-6000:])
 assert 'STORE CATALOG' in run.stderr and 'STORE ERROR' not in run.stderr,run.stderr[-10000:]
 assert set(fixture['requests'])=={'/catalog.txt',*[('/apps/hello/'+(ROOT/'VERSION').read_text().strip()+'/'+name) for name in ('app.ini','files.sha256','app')]},fixture['requests']
 assert 'STORE INSTALLED' in run.stderr and 'STORE STOPPED' not in run.stderr
 assert run.stderr.count('VDEV OPEN FB')==2 and run.stderr.count('EXEC STORE')==1,run.stderr[-6000:]
 assert {p.name:p.read_bytes() for p in (home/'repository').iterdir()}==before
 assert not list((home/'cache').iterdir()) and not list((home/'packages').iterdir()) 
 for name in ('app','app.ini','files.sha256'):assert (home/'apps/hello'/name).read_bytes()==(ROOT/'work/hello-app/package'/name).read_bytes()
 launcher=composition/'external/HOMEBREW/launcher/app'
 launcher_checks=[]
 for mode,expected_output in (('--catalog','store\tNetwork Store\nhello\tHello Walkman\n'),('--check','store VERIFIED\nhello VERIFIED\n')):
  checked=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),mode,str(home/'apps')],capture_output=True,text=True,timeout=10)
  assert checked.returncode==0 and checked.stdout==expected_output,(checked.returncode,checked.stdout,checked.stderr)
  launcher_checks.append({'mode':mode,'stdout':checked.stdout,'exit':checked.returncode})
 executed=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(home/'apps/hello/app'),'--help'],capture_output=True,text=True,timeout=10)
 assert executed.returncode==0 and 'Hello Walkman' in executed.stdout,(executed.returncode,executed.stderr)
 assert hashlib.sha256(store.read_bytes()).hexdigest()==expected
 operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
 assert operations and all('127.0.0.1' in line for line in operations),operations
 parent_frame=(work/'launcher.rgb565').read_bytes();assert len(parent_frame)==240*432*2
 glyphs=[list(map(int,row.split(','))) for row in re.findall(r'\{([0-9,]+)\}',(ROOT/'runtime/native/font.inc').read_text())]
 for n,ch in enumerate('HELLO WALKMAN'):
  if ch==' ':continue
  glyph=glyphs[ord(ch)-ord('A')+10]
  for y in range(7):
   for x in range(5):
    offset=((118+y*2)*240+16+n*12+x*2)*2
    assert (int.from_bytes(parent_frame[offset:offset+2],'little')==0xffff)==bool(glyph[y]&(1<<(4-x)))
 raw=(work/'catalog.rgb565').read_bytes();assert len(raw)==240*432*2;rgb=bytearray()
 for offset in range(0,len(raw),2):
  value=int.from_bytes(raw[offset:offset+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
 (work/'catalog.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
 report={'passed':True,'loopback_network_operations':len(operations),'unchanged_store_sha256':expected,'actual_store_HTTPS_catalog_loaded':True,'actual_store_app_installed':True,'same_parent_launcher_reacquired_and_rescanned':True,'new_app_label_verified_in_same_parent_frame':True,'launcher_checks':launcher_checks,'installed_app_executed_read_only':True,'request_paths':fixture['requests'],'configuration_unchanged':True,'cache_packages_empty':True,'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'runtime/native/font.inc',work/'launcher.rgb565',launcher,*[ROOT/'work/hello-app/package'/name for name in ('app','app.ini','files.sha256')],ROOT/'tools/publish_repository.py',ROOT/'tools/prepare_repository_config.py',work/'catalog.rgb565',work/'catalog.png',ROOT/'sources/native-stock-resolver-probe.json',*[ROOT/'work/stock-resolver-probe'/name for name in resolver['libraries']],Path(__file__),ROOT/'tools/local_store_https.py',ROOT/'tools/test_libc_production_ui.py',ROOT/'tools/fixtures/device_preload.c',store,preload,composition/'manifest.json']},'hardware_tested':False,'limits':['Actual store ELF and real loopback HTTPS; virtual display/touch and test pathname translation.','Actual Hello package installed on temporary host filesystem, not Sony storage.','No physical Wi-Fi, Sony UI/proxy or USB handoff qualification.']}
 write_report(ROOT,'native-production-store-launcher-tests.json',report)
print('Actual selected launcher -> HTTPS store install/cleanup -> same launcher rescan/return passed.')




