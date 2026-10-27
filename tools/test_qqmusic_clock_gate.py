"""Production ARM program composition: clock rejection before platform control."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',required=True);a=p.parse_args()
candidate=(ROOT/a.candidate).resolve();assert candidate.is_relative_to(ROOT/'work')
build=json.loads((candidate/'build.json').read_text())
for name,digest in build['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
work=ROOT/'work/qqmusic-clock-gate';work.mkdir(exist_ok=True)
codec=ROOT/'work/qqmusic-codec';lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
fixture=work/'fixture.o';app=work/'clock-gate.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(candidate),'-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-c','tools/fixtures/qqmusic_clock_gate.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[str(codec/(str(i)+'-'+Path(name).stem+'.o')) for i,name in enumerate(build['sources']) if Path(name).suffix in ('.c','.S') and name!='runtime/apps/qqmusic/qqmusic_main.c']
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),str(fixture),*objects,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
r=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{codec}',str(app)],capture_output=True,text=True,check=True,timeout=15)
assert not any(marker in r.stderr for marker in ('socket(','connect(','sendto(','/tmp/cnmgr_','/contents/'))
(work/'trace.txt').write_text(r.stderr)
report={'passed':True,'production_program_objects':True,'candidate_sha256':build['app_sha256'],'cases':['device2008 date rejected before ensure callback','explicit2008-01-09 diagnostic retained','valid date reaches asynchronous platform preparation','cancel and release callbacks close waiting composition'],'network_or_account_or_device_access':False,'source_hashes':{'fixture':hashlib.sha256((ROOT/'tools/fixtures/qqmusic_clock_gate.c').read_bytes()).hexdigest()}}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
