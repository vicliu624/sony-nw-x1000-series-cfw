"""Silent QEMU mixer model against pinned GPL ARM32 sound-effect ioctl ABI."""
import hashlib,json,os,subprocess,time,tarfile
from app_registry import ROOT
from player_arm_guest import stock_libraries
archive=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
out=ROOT/'work/stock-silent-mixer'/str(time.time_ns());out.mkdir(parents=True)
with tarfile.open(archive,'r:gz') as tar:
 header=tar.extractfile('./include/asm-arm/arch-mp200/icx1087_audio.h').read()
 driver=tar.extractfile('./sound/oss/icx1087-sound.c').read()
(out/'icx1087_audio.h').write_bytes(header)
for name in ('AUDIO_SE_PLAY','AUDIO_SE_STOP','AUDIO_SE_SYNC'):
 branch=driver.decode().split('case '+name+':',1)[1].split('break;',1)[0]
 assert 'if (!s_se_cntl)' in branch and 'return 0;' in branch
sources=['tools/fixtures/stock_silent_mixer_test.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-variable','-Wno-unused-function']
host=out/'host';subprocess.run(['gcc',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
run=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=10);(out/'host.log').write_text(run.stdout+run.stderr)
libs=stock_libraries();arm=out/'test.arm';startup=['runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DTEST_GPL_AUDIO_ABI','-I'+str(out),'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv',*sources,*startup,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(arm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,check=True,timeout=10)
(out/'arm.log').write_text(run.stdout+run.stderr)
assert 'STOCK_SILENT_MIXER_MODEL_PASS' in run.stdout
report=dict(passed=True,host_sanitizers=True,original_libc_arm926=True,pinned_gpl_arm32_ioctl_numbers=True,physical_device_access=False,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*startup,'tools/fixtures/stock_silent_mixer_model.h','tools/test_stock_silent_mixer.py']},
 gpl_header_sha256=hashlib.sha256(header).hexdigest(),gpl_driver_sha256=hashlib.sha256(driver).hexdigest(),
 limits=['Silent PC model with no sound-effect controller, PCM, DSP or sound output.',
 'Original AudioC caller and a complete GUI lifetime are not executed by this bounded contract test.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,report=(out/'report.json').relative_to(ROOT).as_posix()),indent=2))
