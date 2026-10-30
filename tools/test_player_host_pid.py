"""Original-loader preload test for the argument-free PID shim; no device."""
from pathlib import Path
import hashlib,json,os,subprocess
from build_player_host import ROOT,build
library,_,build_report=build();work=ROOT/'work/player-host';lib=ROOT/'work/arm-signal-tests/lib';extra=ROOT/'work/player-sqlite-ro';app=work/'pid-consumer.arm'
sources=['tools/fixtures/player_host_pid.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(extra/'libdl.so.2'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
env=dict(os.environ);env.pop('LD_PRELOAD',None);env['QEMU_UNSET_ENV']='LD_LIBRARY_PATH'
cases=[]
for preloaded in (False,True):
    command=['qemu-arm','-cpu','arm926','-strace']
    if preloaded:command+=['-E','LD_PRELOAD='+str(library)]
    command += [str(lib/'ld-linux.so.3'),'--library-path',str(ROOT/'work/stock-resolver-probe')+':'+str(extra)+':'+str(lib),str(app)]
    if preloaded:command+=['--preloaded']
    run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=15)
    (work/('preload.log' if preloaded else 'baseline.log')).write_text(run.stdout+run.stderr)
    assert run.returncode==0,run.stdout+run.stderr[-4000:]
    assert not any(value in run.stderr for value in ('/dev/','/contents/','/db/','socket('))
    cases.append(dict(preloaded=preloaded,stdout=run.stdout))
report=dict(passed=True,actual_sony_loader=True,actual_pid_interposition=True,stock_app_executed=False,device_accessed=False,cases=cases,library_sha256=build_report['library_sha256'],
 source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['tools/test_player_host_pid.py']},
 limits=['This checks unrelated-PID pass-through and original-loader constructor behavior, not the anchored owner callback or hardware installation.'])
(work/'pid-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
