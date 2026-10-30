"""Sony-libc ARM startup wrapper execs a static host observer; no Sony app."""
from pathlib import Path
import hashlib,json,os,subprocess,shutil
from app_registry import ROOT
w=ROOT/'work/player-stock-exec';w.mkdir(exist_ok=True)
observer=w/'observer';subprocess.run(['gcc-12','-std=c99','-Os','-Wall','-Wextra','-Werror','-static',str(ROOT/'tools/fixtures/player_exec_observer.c'),'-o',str(observer)],check=True)
lib=ROOT/'work/arm-signal-tests/lib'
# A readable inert ARM DSO tests environment composition without hardware code.
inert=w/'inert.c';inert.write_text('int xw_exec_fixture(void){return 7;}\n')
preload=w/'inert.so';subprocess.run(['arm-linux-gnueabi-gcc','-marm','-march=armv5te','-fPIC','-nostdlib','-shared','-Wl,--hash-style=sysv',str(inert),'-o',str(preload)],check=True)
prior_library=w/'prior.so';shutil.copyfile(preload,prior_library)
cases=[]
for present in (False,True):
 app=w/('wrapper-'+str(int(present))+'.arm');path=preload if present else w/'absent.so'
 sources=['runtime/platform/player/stock_exec.c','runtime/store/start.c','runtime/store/start.S']
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-DXW_PLAYER_STOCK_EXECUTABLE="'+str(observer)+'"','-DXW_PLAYER_PRELOAD_LIBRARY="'+str(path)+'"',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
 for prior in ('',str(preload),str(preload)+' '+str(preload),str(prior_library),str(prior_library)+':'+str(preload)):
  env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH',XW_TEST_KEEP='preserved');env.pop('LD_PRELOAD',None)
  command=['qemu-arm','-cpu','arm926','-E','LD_PRELOAD='+prior,str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),'review argument']
  process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  stdout,stderr=process.communicate(timeout=15);assert process.returncode==0,stdout+stderr
  rows=stdout.splitlines();assert len(rows)==5,(rows,stderr)
  assert int(rows[0])==process.pid and rows[1]==str(app) and rows[2]=='review argument' and rows[3]=='preserved',rows
  expected=prior if not present or str(preload) in prior.replace(':',' ').split() else str(preload)+(':'+prior if prior else '')
  assert rows[4]==expected,(rows,expected)
  cases.append(dict(library_present=present,prior=prior,pid_preserved=True,arguments_environment_preserved=True))
report=dict(passed=True,actual_sony_libc_wrapper=True,exec_replaces_process=True,cases=cases,stock_app_executed=False,device_accessed=False,installed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/fixtures/player_exec_observer.c','tools/test_player_stock_exec.py']},limits=['The ARM wrapper execs a static host observer, not SpiderApp.','No SysMgr startup, composite firmware, power state, live service or hardware integration is qualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
