"""Build an explicit autonomous native experiment; never installs or runs RF."""
from pathlib import Path
import hashlib,json,subprocess,sys,shutil
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from generate_espnow_full_profile import render
OUT=ROOT/'work/autonomous-espnow-test';OUT.mkdir(exist_ok=True)
radio=ROOT/'work/espnow-full-radio-review-3';manifest=json.loads((radio/'manifest.json').read_text())
for name,digest in manifest['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
(OUT/'full_profile.h').write_text(render(radio))
header=['static const struct stock_input exchange_inputs[]={']
for name in ('sd8686.bin','helper_sd.bin'):
    data=(radio/'candidate'/name).read_bytes();expected=manifest['candidate_sha256'] if name=='sd8686.bin' else manifest['helper_sha256'];assert hashlib.sha256(data).hexdigest()==expected
    header.append('{'+json.dumps('/contents/HOMEBREW/data/espnow-test/candidate/'+name)+','+str(len(data))+',{'+','.join(map(str,bytes.fromhex(expected)))+'}},')
(OUT/'exchange_inputs.h').write_text('\n'.join(header+['};'])+'\n')
subprocess.run([sys.executable,str(ROOT/'runtime/platform/espnow/build_library.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip();sdk=ROOT/'work/espnow-native-library'/version/'sdk';library=json.loads((sdk/'build.json').read_text());archive=sdk/'lib/libxnow.a'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==library['archive_sha256']
for name,digest in library['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe'
sources=['runtime/apps/espnow-test/main.c','runtime/apps/espnow-test/runner.c','runtime/apps/espnow-test/detached.c','runtime/platform/espnow/xnow_owner_gate.c','runtime/platform/espnow/xnow_loader_job.c','runtime/store/start.c','runtime/store/start.S']
binary=OUT/'espnow-test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-unused-function','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-DXNOW_CANDIDATE_DIRECTORY="/contents/HOMEBREW/data/espnow-test/candidate"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),'-I'+str(ROOT/'runtime/platform/espnow'),'-I'+str(ROOT/'work/espnow-stock-reload-lab'),*sources,str(archive),str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(resolver/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(resolver/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver),str(binary)]
help_run=subprocess.run(base+['--help'],capture_output=True,text=True,check=True,timeout=15)
for args in ([],['--detach-rx'],['--detach-rx','ffffffffffff','--charger-confirmed','--exclusive-radio-confirmed']):
    check=subprocess.run(base+args,capture_output=True,text=True,timeout=15);assert check.returncode==64
shutil.copy2(ROOT/'runtime/apps/espnow-test/README.md',OUT/'README.md')
report={'built':True,'version':(ROOT/'runtime/apps/espnow-test/VERSION').read_text().strip(),'bytes':binary.stat().st_size,'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'arm_help_passed':True,'no_args_and_invalid_invocations_refused':True,'library_version':version,'radio_candidate_sha256':manifest['candidate_sha256'],'terminal_independent_after_detach':True,'user_journal_limit_bytes':8192,'test_window_seconds':60,'physical_radio_qualified':False,'original_apf_usb_sleep_ownership_qualified':False,'device_written':False,'radio_loaded':False,'firmware_created':False,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/apps/espnow-test/runner.h','runtime/apps/espnow-test/build.py','runtime/platform/espnow/exchange_lab.c','runtime/platform/espnow/stock_reload_lab.c','runtime/platform/espnow/stock_wifi_session.c']}}
(OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
