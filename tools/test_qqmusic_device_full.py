"""Actual full native main + workspace + import binding, simulated bottom IO.
No account/login request and no physical device. Reuses exact candidate objects.
"""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',default='work/qqmusic-device-full-11');args=parser.parse_args()
candidate=(ROOT/args.candidate).resolve();assert candidate.is_relative_to(ROOT/'work')
build=json.loads((candidate/'build.json').read_text())
assert build['imports_enabled'] and not build['host_session_fixture']
for path,digest in build['sources'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
work=ROOT/'work/qqmusic-device-full-check';work.mkdir(exist_ok=True)
header=(candidate/'qqmusic_profile.h').read_text().splitlines()
header=['#define QQ_PROFILE_SOURCE "/dev/mock-user"' if line.startswith('#define QQ_PROFILE_SOURCE ') else line for line in header]
(work/'qqmusic_profile.h').write_text('\n'.join(header)+'\n')
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';codec=ROOT/'work/qqmusic-codec'
fixture=work/'main.o'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DQQ_NATIVE_FULL','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections','-I'+str(work),'-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb','-c','tools/fixtures/qqmusic_native_boot.c','-o',str(fixture)],cwd=ROOT,check=True)
objects=[]
for i,path in enumerate(build['sources']):
    if Path(path).suffix not in ('.c','.S'):continue
    if path in ('runtime/apps/qqmusic/qqmusic_main.c','runtime/native/syscalls.S'):continue
    obj=codec/(str(i)+'-'+Path(path).stem+'.o');assert obj.is_file();objects.append(str(obj))
app=work/'device-main.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=qq_runtime_bind_import',str(fixture),*objects,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(codec/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
for fault in range(4):
    with tempfile.TemporaryDirectory(prefix='case-',dir=work) as directory:
        shutil.copyfile(ROOT/'work/qqmusic-font/QQMusicUI.otf',Path(directory)/'font.otf')
        result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{codec}',str(app),directory,str(fault)],cwd=ROOT,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(fault,result.returncode,result.stderr[-2000:])
        if fault==0:
            assert any(str(FONT_BYTES) in line and 'PROT_READ,MAP_PRIVATE' in line for line in result.stderr.splitlines() if 'mmap' in line)
            (work/'mapped-font.trace').write_text(result.stderr)
        frame=Path(directory)/'frame.rgb565'
        if frame.exists():shutil.copyfile(frame,work/'first-frame.rgb565');frame.unlink()
        assert not list(Path(directory).iterdir())
report={'passed':True,'candidate_sha256':build['app_sha256'],'actual_production_main':True,'production_workspace_and_import_binding':True,'same_candidate_module_objects':True,'mount_display_and_touch_simulated':True,'profile_source_for_fixture':'/dev/mock-user','real_account_accessed':False,'physical_device_accessed':False,'checks':['native entry attaches import begin/poll/cancel','read-only volume rejects workspace creation','second instance cannot acquire same flock','stop rejects further IO','replaced lock inode fails ownership check','symlink lock rejected without target write','normal signal shutdown releases workspace and devices','display failure cleanup','device close failure propagation','signal setup failure before device open'],'fixture_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['tools/fixtures/qqmusic_native_boot.c','tools/fixtures/qqmusic_entry_boot.c','tools/fixtures/qqmusic_volume.c']}}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
