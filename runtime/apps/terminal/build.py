"""Build a personal offline candidate; never writes to or executes on a player."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from sdk_services import compiler as sdk_compiler
sdk_run = sdk_compiler(Path(__file__).resolve().parent)
from pathlib import Path
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
import struct
import zlib
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[3]
os.chdir(ROOT)
work=ROOT/'work/terminal-review'
work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
crypto=ROOT/'work/external-tls-probe/bearssl-0.6'
archive=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
host_archive=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'
assert archive.is_file()
# Compiler/binutils revisions may change archive bytes. Pin the upstream input,
# and retain the actual compiled archive digest in build.json instead.
assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
version=(ROOT/'runtime/apps/terminal/VERSION').read_text().strip()
flags=['-DHB_STORE_SONY_LIBC','-DHB_BUILD_VERSION="'+version+'"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(crypto/'inc')]
flags.append('-DHB_USE_POSIX_DEVICE_IO')
startup=['runtime/store/start.c','runtime/store/start.S']
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/apps/terminal/terminal_firewall.c']
ui=['runtime/apps/terminal/terminal_app.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c']
sources=['runtime/apps/terminal/terminal.c',*ui,*bridge,*startup]
app=work/'terminal.arm'
def build(out,files):
    sdk_run(['arm-linux-gnueabi-gcc',*flags,*files,str(archive),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(out)],check=True)
build(app,sources)
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
for option in ('--help','--version','--selftest'):
    result=sdk_run(base+[str(app),option],capture_output=True,text=True,check=True,timeout=15)
    print(result.stdout.strip())
bad=sdk_run(base+[str(app),'--serve-test'],capture_output=True,timeout=15)
assert bad.returncode==64
elf=ELFFile(io.BytesIO(app.read_bytes()))
needed=[x.needed for x in elf.get_section_by_name('.dynamic').iter_tags() if x.entry.d_tag=='DT_NEEDED']
assert needed==['libc.so.6'],needed
undefined=subprocess.check_output(['arm-linux-gnueabi-nm','-u',str(app)],text=True)
assert '__ioctl_time64' not in undefined and '__clock_gettime64' not in undefined
fixture=work/'server-tests.arm'
build(fixture,['runtime/apps/terminal/terminal.c','tools/fixtures/terminal_server.c',*bridge,*startup])
host=work/'server-tests.host'
sdk_run(['gcc','-D_DEFAULT_SOURCE','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-no-pie','-I'+str(crypto/'inc'),'runtime/apps/terminal/terminal.c','runtime/apps/terminal/terminal_firewall.c','tools/fixtures/terminal_server.c',str(host_archive),'-o',str(host)],check=True)
gate=work/'firewall-tests.arm'
build(gate,['tools/fixtures/terminal_firewall.c',*bridge,*startup])
sdk_run(base+[str(gate)],check=True,timeout=15)
folder=work/'package/HOMEBREW/apps/terminal'
folder.mkdir(parents=True,exist_ok=True)
# Per-local-installation EC identity; never a checked-in/shared sample private key.
# Rebuild preserves this identity so the PC certificate pin stays stable.
identity=work/'private-identity'
identity.mkdir(mode=0o700,exist_ok=True)
key=identity/'server-key.pem'
if not key.exists():
    sdk_run(['openssl','ecparam','-name','prime256v1','-genkey','-noout','-out',str(key)],check=True)
    key.chmod(0o600)
    sdk_run(['openssl','req','-new','-x509','-sha256','-days','3650','-key',str(key),'-subj','/CN=X1060 WiFi Terminal/','-out',str(identity/'server-cert.pem')],check=True)
sdk_run(['openssl','ec','-in',str(key),'-outform','DER','-out',str(folder/'server-key.der')],check=True,capture_output=True)
sdk_run(['openssl','x509','-in',str(identity/'server-cert.pem'),'-outform','DER','-out',str(folder/'server-cert.der')],check=True)
pin=hashlib.sha256((folder/'server-cert.der').read_bytes()).hexdigest()
(work/'server-cert.sha256').write_text(pin+'\n')
sdk_run([sys.executable,'tools/test_terminal.py'],check=True)
render=work/'ui-tests.arm'
sdk_run(['arm-linux-gnueabi-gcc',*flags,'-DHB_TERMINAL_UI_TEST','runtime/apps/terminal/terminal.c','runtime/apps/terminal/terminal_app.c','runtime/native/frontend.c','runtime/native/linux_signals_posix.c','tools/fixtures/terminal_ui.c',*bridge,*startup,str(archive),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(render)],check=True)
sdk_run(base+[str(render),'--render-test',str(folder)],check=True,timeout=15)
raw=(work/'screen.rgb565').read_bytes();assert len(raw)==240*432*2
rgb=bytearray()
for y in range(432):
    rgb.append(0)
    for x in range(240):
        pixel=struct.unpack_from('<H',raw,(y*240+x)*2)[0]
        rgb.extend((((pixel>>11)&31)*255//31,((pixel>>5)&63)*255//63,(pixel&31)*255//31))
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
(work/'screen.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rgb))+chunk(b'IEND',b''))
shutil.copyfile(app,folder/'app')
digest=hashlib.sha256(app.read_bytes()).hexdigest()
(folder/'app.ini').write_text(f'api=1\nid=terminal\nname=WiFi Terminal\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={app.stat().st_size}\nsha256={digest}\n')
inventory=[folder/'app',folder/'app.ini',folder/'server-cert.der',folder/'server-key.der']
(folder/'files.sha256').write_text('HBFILES1\n'+''.join(hashlib.sha256(p.read_bytes()).hexdigest()+f' {p.stat().st_size} {p.name}\n' for p in inventory))
checked=sdk_run(base+[str(ROOT/'work/libc-launcher-review/launcher.elf'),'--check',str(work/'package/HOMEBREW/apps')],capture_output=True,text=True,check=True,timeout=15)
assert checked.stdout=='terminal VERIFIED\n',checked.stdout
report={'software_checks_passed':True,'hardware_tested':False,'device_written':False,'system_partition_added_bytes':0,'app_bytes':app.stat().st_size,'installed_app_bytes':sum(p.stat().st_size for p in folder.iterdir()),'certificate_pin':pin,'needed':needed,'transport':'WiFi / TCP 2323 / TLS1.2 ECDHE-ECDSA AES128-GCM','bearssl_arm_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'ui_render_and_touch_return_passed':True,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/apps/terminal/terminal.h','runtime/native/font.inc','runtime/native/frontend.h','runtime/native/linux_devices.h','runtime/native/linux_signals.h','runtime/native/linux_device_io.h','runtime/store/target_abi.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h','tools/fixtures/terminal_server.c','tools/fixtures/terminal_ui.c','docs/apps/TERMINAL.md','tools/terminal_client.py','tools/test_terminal.py','tools/build_terminal.py']}}
report['temporary_firewall_rule_implemented']=True
report['firewall_lifecycle_fixture_passed']=True
for name in ['runtime/apps/terminal/terminal_firewall.h','tools/fixtures/terminal_firewall.c']:
    report['sources'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
files={}
for p in folder.iterdir():files['HOMEBREW/apps/terminal/'+p.name]=p.read_bytes()
files['computer/terminal_client.py']=(ROOT/'tools/terminal_client.py').read_bytes()
files['computer/server-cert.sha256']=(work/'server-cert.sha256').read_bytes()
files['README.md']=(ROOT/'docs/apps/TERMINAL.md').read_bytes()
files['LICENSE-BearSSL.txt']=(crypto/'LICENSE.txt').read_bytes()
files['build.json']=(work/'build.json').read_bytes()
files['tests.json']=(work/'tests.json').read_bytes()
files['preview/screen.png']=(work/'screen.png').read_bytes()
for p in report['sources']:files['source/'+p]=(ROOT/p).read_bytes()
zip_path=work/f'WiFi-Terminal-{version}-personal-experimental.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for name,content in sorted(files.items()):z.writestr(name,content)
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    for name,content in files.items():assert z.read(name)==content
print(json.dumps({**report,'zip':str(zip_path.relative_to(ROOT)),'zip_bytes':zip_path.stat().st_size},indent=2))
