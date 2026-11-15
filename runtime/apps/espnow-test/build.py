"""Build an explicit autonomous native experiment; never installs or runs RF."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,shutil
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'runtime/platform/espnow'))
from build_library import build_sdk
from generate_espnow_full_profile import profile_header, reviewed_radio
from owner_native_profile import file_initializer, render as render_native_profile, stock_header
from component_receipts import native_sdk_build, private
from sdk_build import fresh_work

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--radio-review', type=Path, default=ROOT/'work/espnow-full-radio-review-3',
                    help='Current scalar full-radio review directory under work/')
parser.add_argument('--sdk-review', type=Path, help='Reuse a verified native SDK build.json')
parser.add_argument('--output', type=Path, help='New build directory under work/')
args = parser.parse_args()
payload, manifest = reviewed_radio(args.radio_review)
radio = payload.parent
if manifest.get('frame_transactions') or manifest.get('bulk_word_commands'):
    parser.error('The finite experiment requires the scalar radio profile')
stock = private('work/upg-jp/verified-3.bin')
stock_inputs = stock_header(stock)
sdk_review,archive,library=native_sdk_build(args.sdk_review or build_sdk()[0])
if args.output is None:
    OUT=ROOT/'work/autonomous-espnow-test';OUT.mkdir(exist_ok=True)
else:
    OUT=fresh_work(args.output)
(OUT/'full_profile.h').write_text(profile_header(manifest))
header=['static const struct stock_input exchange_inputs[]={']
for name in ('sd8686.bin','helper_sd.bin'):
    data=(radio/'candidate'/name).read_bytes();expected=manifest['candidate_sha256'] if name=='sd8686.bin' else manifest['helper_sha256']
    if hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('Radio artifact changed: '+name)
    header.append(file_initializer('/contents/HOMEBREW/data/espnow-test/candidate/'+name, data))
(OUT/'exchange_inputs.h').write_text('\n'.join(header+['};'])+'\n')
(OUT/'native_inputs.h').write_text(render_native_profile(
    stock_inputs,
    (OUT/'exchange_inputs.h').read_text(encoding='utf-8')), encoding='utf-8')
version=library['version']
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe'
sources=['runtime/apps/espnow-test/main.c','runtime/platform/espnow/native_environment.c','runtime/apps/espnow-test/runner.c','runtime/apps/espnow-test/detached.c','runtime/platform/espnow/xnow_owner_gate.c','runtime/platform/espnow/xnow_loader_job.c','runtime/store/start.c','runtime/store/start.S']
binary=OUT/'espnow-test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-unused-function','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-DXNOW_USER_DATA_LEAF="espnow-test"','-DXNOW_CANDIDATE_DIRECTORY="/contents/HOMEBREW/data/espnow-test/candidate"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),'-I'+str(ROOT/'runtime/platform/espnow'),*sources,str(archive),str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(resolver/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(resolver/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver),str(binary)]
help_run=subprocess.run(base+['--help'],capture_output=True,text=True,check=True,timeout=15)
for args in ([],['--detach-rx'],['--detach-rx','ffffffffffff','--charger-confirmed','--exclusive-radio-confirmed']):
    check=subprocess.run(base+args,capture_output=True,text=True,timeout=15);assert check.returncode==64
shutil.copy2(ROOT/'runtime/apps/espnow-test/README.md',OUT/'README.md')
report={'built':True,'version':(ROOT/'runtime/apps/espnow-test/VERSION').read_text().strip(),'bytes':binary.stat().st_size,'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'arm_help_passed':True,'no_args_and_invalid_invocations_refused':True,'library_version':version,'radio_candidate_sha256':manifest['candidate_sha256'],'terminal_independent_after_detach':True,'user_journal_limit_bytes':8192,'test_window_seconds':60,'physical_radio_qualified':False,'original_apf_usb_sleep_ownership_qualified':False,'device_written':False,'radio_loaded':False,'firmware_created':False,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/apps/espnow-test/runner.h','runtime/apps/espnow-test/build.py','runtime/platform/espnow/native_environment.h','runtime/platform/espnow/native_entry.h','tools/owner_native_profile.py',str((OUT/'native_inputs.h').relative_to(ROOT))]}}
report['sdk_review']=sdk_review.relative_to(ROOT).as_posix()
report['radio_review']=(radio/'manifest.json').relative_to(ROOT).as_posix()
report['source_sha256'].update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (sdk_review,archive,radio/'manifest.json',payload,stock,OUT/'full_profile.h')})
(OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
