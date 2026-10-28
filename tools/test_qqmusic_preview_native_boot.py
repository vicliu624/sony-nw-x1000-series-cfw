"""Actual candidate objects/main preview branch, simulated display/mounts only."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--candidate',default='work/qqmusic-device-preview-1');args=p.parse_args()
if os.geteuid()!=0:raise SystemExit('Use a privileged isolated development environment for the real global /proc FD scan.')
candidate=(ROOT/args.candidate).resolve();assert candidate.is_relative_to(ROOT/'work')
build=json.loads((candidate/'build.json').read_text());assert build['audio_preview_enabled'] and build['imports_enabled'] and not build['host_session_fixture']
for name,digest in build['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
w=ROOT/'work/qqmusic-preview-native-boot';w.mkdir(exist_ok=True)
header=(candidate/'qqmusic_profile.h').read_text().splitlines();header=['#define QQ_PROFILE_SOURCE "/dev/mock-user"' if s.startswith('#define QQ_PROFILE_SOURCE ') else s for s in header]
(w/'qqmusic_profile.h').write_text('\n'.join(header)+'\n');shutil.copyfile(candidate/'qqmusic_preview_profile.h',w/'qqmusic_preview_profile.h')
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';codec=ROOT/'work/qqmusic-codec';fixture=w/'main.o'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DQQ_NATIVE_FULL','-DQQ_NATIVE_PREVIEW','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(w),'-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb','-c','tools/fixtures/qqmusic_native_boot.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[]
for i,name in enumerate(build['sources']):
 if Path(name).suffix not in ('.c','.S') or name in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/native/syscalls.S'):continue
 obj=codec/(str(i)+'-'+Path(name).stem+'.o');assert obj.is_file();objects.append(str(obj))
app=w/'preview-main.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=qq_runtime_bind_import,--wrap=qq_runtime_bind_preview,--wrap=qq_preview_runtime_run',str(fixture),*objects,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
for fault in range(4):
 with tempfile.TemporaryDirectory(prefix='case-',dir=w) as d:
  shutil.copyfile(ROOT/'work/qqmusic-font/QQMusicUI.otf',Path(d)/'font.otf')
  r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{codec}',str(app),d,str(fault)],cwd=ROOT,capture_output=True,timeout=25)
  assert r.returncode==0,(fault,r.returncode,r.stderr[-2200:])
  frame=Path(d)/'frame.rgb565'
  if frame.exists():shutil.copyfile(frame,w/'first-frame.rgb565');frame.unlink()
  assert not list(Path(d).iterdir())
report={'passed':True,'candidate_sha256':build['app_sha256'],'actual_preview_main_branch':True,'same_candidate_module_objects':True,'real_supervisor_fork_reap_and_guard_scan':True,'simulated_mount_display_touch':True,'cases':4,'physical_device_accessed':False,'account_accessed':False,'limits':['No preview is started in this boot test: no PCM device open or ioctl.','Audio output, download chain and physical restoration remain separate acceptance gates.'],'fixture_sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['tools/fixtures/qqmusic_native_boot.c','tools/fixtures/qqmusic_entry_boot.c','tools/fixtures/qqmusic_volume.c']}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
