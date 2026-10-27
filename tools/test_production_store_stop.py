"""Actual unchanged r3 store: fetch HTTPS catalog with real TLS, virtual devices."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import signal,time,os,contextlib,hashlib,io,json,runpy,shutil,subprocess,tempfile,re,struct,zlib
from local_store_https import repository_fixture
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_libc_production_ui.py'))
work=work_area(ROOT,'production-store-stop-review')
composition=base['composition'];store=composition/'external/HOMEBREW/apps/store/app';preload=base['preload'];lib=base['lib']
expected=next(r['sha256'] for r in base['manifest']['files'] if r['path']=='external/HOMEBREW/apps/store/app');assert hashlib.sha256(store.read_bytes()).hexdigest()==expected
with repository_fixture(ROOT/'work/hello-app/package',hold_path='/catalog.txt') as fixture:
 prefix=fixture['area']/'sysroot';(prefix/'lib').mkdir(parents=True)
 resolver=json.loads((ROOT/'sources/native-stock-resolver-probe.json').read_text())
 for name in ('libc.so.6','ld-linux.so.3','libcares.so.2','librt.so.1','libpthread.so.0'):
  original=ROOT/'work/stock-resolver-probe'/name;assert hashlib.sha256(original.read_bytes()).hexdigest()==resolver['libraries'][name]['sha256'];shutil.copyfile(original,prefix/'lib'/name)
 home=prefix/'contents/HOMEBREW';home.mkdir(parents=True)
 shutil.copytree(fixture['configuration'],home/'repository');(home/'cache').mkdir();(home/'packages').mkdir();(home/'apps').mkdir()
 before={p.name:p.read_bytes() for p in (home/'repository').iterdir()}
 shutil.copytree(composition/'external/HOMEBREW/apps/store',home/'apps/store')
 launcher=composition/'external/HOMEBREW/launcher/app'
 settings={'LD_PRELOAD':str(preload),'HB_TEST_MODE':'loop','HB_TEST_TARGET':'store','HB_TEST_NETWORK':'install','HB_TEST_STOP':'1','HB_TEST_TRACE_CHILD':'1','HB_TEST_PREFIX':str(prefix),'HB_TEST_PRELOAD':str(preload),'HB_TEST_CHILD_FRAME':str(work/'catalog.rgb565'),'HB_TEST_FRAME':str(work/'launcher.rgb565')}
 command=['qemu-arm','-strace','-cpu','arm926','-L',str(prefix),'-0','/contents/HOMEBREW/launcher/app']
 for key,value in settings.items():command+=['-E',key+'='+value]
 log=open(work/'last-run.log','w');out=open(work/'stdout.log','w')
 process=subprocess.Popen(command+[str(launcher),'--native'],cwd=ROOT,stdout=out,stderr=log,text=True)
 try:
  assert fixture['requested'].wait(10),'Actual store never requested catalog'
  assert process.poll() is None
  process.send_signal(signal.SIGTERM)
  process.wait(timeout=10)
 finally:
  fixture['proceed'].set()
  if process.poll() is None:
   children=Path(f'/proc/{process.pid}/task/{process.pid}/children')
   for value in children.read_text().split() if children.exists() else []:
    try:
     if str(prefix).encode() in (Path('/proc')/value/'cmdline').read_bytes():os.kill(int(value),signal.SIGKILL)
    except (FileNotFoundError,ProcessLookupError):pass
   process.kill();process.wait(timeout=5)
  log.close();out.close()
 stdout=(work/'stdout.log').read_text();stderr=(work/'last-run.log').read_text()
 assert process.returncode==0 and not stdout,(process.returncode,stderr[-8000:])
 assert stderr.count('VDEV OPEN FB')==1 and stderr.count('EXEC STORE')==1,stderr[-10000:]
 assert stderr.count('RELEASE COMPLETE')==2 and 'STORE INSTALLED' not in stderr
 assert re.search(r'-[0-9]+,SIGTERM',stderr) and ('si_pid='+str(process.pid)) in stderr and stderr.count('sigreturn(')>=2,stderr[-8000:]
 assert fixture['requests']==['/catalog.txt']
 assert {p.name:p.read_bytes() for p in (home/'repository').iterdir()}==before
 assert {p.name for p in (home/'apps').iterdir()}=={'store'}
 assert not list((home/'packages').iterdir())
 cache=[{'name':p.name,'bytes':p.stat().st_size} for p in (home/'cache').iterdir()]
 assert len(cache)<=1 and all(p['name'].startswith('.fetch-') and p['bytes']<=len((fixture['web']/'catalog.txt').read_bytes()) for p in cache)
 report={'passed':True,'actual_launcher_and_store':True,'SIGTERM_during_pending_HTTPS_response':True,'child_group_SIGTERM_forwarded':True,'no_parent_device_reacquire_after_stop':True,'parent_and_child_device_cleanup_observed':True,'parent_exit':process.returncode,'no_app_installed':True,'remaining_owned_cache':cache,'trace':stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tools/local_store_https.py',ROOT/'tools/test_libc_production_ui.py',ROOT/'tools/fixtures/device_preload.c',store,launcher,preload,composition/'manifest.json']},'hardware_tested':False,'limits':['Actual ARM artifacts, QEMU host process/signal delivery; devices and paths virtual.','Stop injected while catalog HTTP response withheld; not every install/flash interruption point.','Not physical USB unmount/export, Sony proxy or GUI handoff qualification.']}
 write_report(ROOT,'native-production-store-stop-tests.json',report)
print('Actual launcher/store: SIGTERM during pending HTTPS response cleans devices and exits without reacquire.')

