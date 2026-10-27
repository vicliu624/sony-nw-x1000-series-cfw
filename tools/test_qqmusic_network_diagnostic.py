"""Preserve DNS/TLS/HTTP numeric errors through transport cleanup; no requests."""
from pathlib import Path
import argparse,json,resource,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-network-diagnostic';work.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',default='work/qqmusic-device-full-11');args=parser.parse_args()
build=json.loads((ROOT/args.candidate/'build.json').read_text());codec=ROOT/'work/qqmusic-codec';lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
fixture=work/'diagnostic.o';app=work/'diagnostic.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-c','tools/fixtures/qqmusic_network_diagnostic.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[str(codec/(str(i)+'-'+Path(name).stem+'.o')) for i,name in enumerate(build['sources']) if Path(name).suffix in ('.c','.S') and name not in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/apps/qqmusic/qqmusic_network.c')]
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),str(fixture),*objects,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{codec}',str(app)],check=True,timeout=15)
report={'passed':True,'actual_arm_transport_error_cleanup':True,'cases':['DNS timeout numeric status survives cancel','TLS certificate error survives erasure of engine','HTTP503 retained independently from TLS error','device2008 date rejects request before DNS and retains explicit date','clock diagnostic survives cancellation','unreadable clock is distinguished without fabricated date','TLS certificate date error is separate from other TLS failures','HTTP200 bootstrap with device8h ahead becomes explicit clock skew','cached artwork Date cannot trigger a clock-skew rejection'],'network_or_real_account_accessed':False}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
