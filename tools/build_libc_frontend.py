"""Build an offline-only launcher using stock libc and POSIX process calls."""
from pathlib import Path
import hashlib,json,subprocess,shutil,argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-output',default='work/libc-launcher-review');parser.add_argument('--managed-radio-review',action='store_true');options=parser.parse_args()
work=(ROOT/options.review_output).resolve();assert work.is_relative_to(ROOT/'work') and work!=ROOT/'work'
assert not any(part.startswith(('integration-','product-review-','network-external-','libc-product-review-')) for part in work.relative_to(ROOT/'work').parts)
if options.managed_radio_review and (options.review_output=='work/libc-launcher-review' or (work/'launcher.elf').exists()):raise ValueError('Managed review requires a distinct unused output directory')
work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
names=['frontend.c','sony_bridge.c','sha256.c','selftest.c','platform_arm.c','app_process.c','home_key.c','linux_process_posix.c','linux_devices.c','linux_device_io_posix.c','app_catalog.c','linux_file_ops_posix.c','linux_signals_posix.c','libc_main.c']
files=['runtime/native/'+name for name in names]+['runtime/store/start.c','runtime/store/start.S']
artifact=work/'launcher.elf';base_version=(ROOT/'runtime/native/VERSION').read_text().strip();version='0.1.0-alpha.1+managed-radio-review' if options.managed_radio_review else base_version
flags=['-DHB_USE_POSIX_FILES','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-DHB_BUILD_VERSION="'+version+'"','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none']
if options.managed_radio_review:
 flags+=['-DHB_MANAGED_RADIO_REVIEW','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0']
 files+=['runtime/platform/espnow/'+name+'.c' for name in ('xnow_launcher_bridge','xnow_managed_process','xnow_handoff')]+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
objects=[];object_dir=work/'objects';object_dir.mkdir(exist_ok=True)
for index,source in enumerate(files):
 obj=object_dir/(str(index).zfill(2)+'-'+Path(source).stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*[flag for flag in flags if not flag.startswith('-Wl,')],'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*objects,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact)]
apps=work/'apps';apps.mkdir(exist_ok=True)
shutil.copytree(ROOT/'work/hello-app/package',apps/'hello',dirs_exist_ok=True)
checks={}
for args in [['--selftest'],['--version'],['--catalog',str(apps)],['--check',str(apps)]]:
    result=subprocess.run(base+args,cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,(args,result.stdout,result.stderr)
    checks[' '.join(args)]=result.stdout
assert checks['--version']==version+'\n'
assert 'VERIFIED' in checks['--check '+str(apps)]
dynamic=subprocess.run(['arm-linux-gnueabi-readelf','-d',str(artifact)],capture_output=True,text=True,check=True).stdout
assert 'Shared library: [libc.so.6]' in dynamic
assert 'libcnmgr' not in dynamic and 'libbearssl' not in dynamic
undefined=subprocess.run(['arm-linux-gnueabi-nm','-D','--undefined-only',str(artifact)],capture_output=True,text=True,check=True).stdout
for symbol in ('fork','execve','waitpid','setpgid','kill','signal','open64','read','write','close','readlink','ioctl','mmap64','munmap','poll','opendir','readdir64','closedir','llseek'):
    assert any(line.split()[-1].split('@')[0]==symbol for line in undefined.splitlines())
symbol_table=subprocess.run(['arm-linux-gnueabi-nm',str(artifact)],capture_output=True,text=True,check=True).stdout
assert 'x1000_oabi_call' not in symbol_table and 'x1000_rt_sigreturn' not in symbol_table
if options.managed_radio_review:
 for name in ('cnmgr_', 'br_ccm_', 'xnow_full_control_finished'):assert name not in undefined
tracked=[apps/'hello/app',apps/'hello/app.ini']+[ROOT/f for f in files]+list((ROOT/'runtime/native').glob('*.h'))+[ROOT/'runtime/native/font.inc',ROOT/'VERSION',ROOT/'runtime/native/VERSION',Path(__file__),lib/'libc.so.6',lib/'ld-linux.so.3']
if options.managed_radio_review:
 tracked += [ROOT/'runtime/platform/espnow'/n for n in ('xnow_launcher_bridge.h','xnow_managed_process.h','xnow_handoff.h','xnow_mailbox.h')]+[ROOT/'runtime/store/target_abi.h',ROOT/'runtime/store/stock_fs_bridge.h',ROOT/'runtime/store/stock_stat64.h']
report={'passed':True,'managed_radio_review':options.managed_radio_review,'base_native_version':base_version,'profile':'stock-libc-runtime-review','version':version,'artifact':str(artifact.relative_to(ROOT)),'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'checks':checks,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'firmware_created':False,'hardware_tested':False,'limits':['Catalog/selftest only; no successful app execution through this launcher yet.','Launcher links stock libc for all OS operations; driver protocol remains target-specific.','Not a replacement for the protected candidate.']}
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))







