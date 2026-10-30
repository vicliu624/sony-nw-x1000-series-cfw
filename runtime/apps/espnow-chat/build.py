"""PC-only local native chat package/preview build. No device operations."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from elftools.elf.elffile import ELFFile
from sdk_services import compiler
sdk_run=compiler(ROOT/'runtime/apps/espnow-chat')
OUT=ROOT/'work/espnow-chat-app';OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((LIB/name).read_bytes()).hexdigest()==digest
library_version=(ROOT/'runtime/platform/espnow/VERSION').read_text().strip()
subprocess.run([sys.executable,str(ROOT/'runtime/platform/espnow/build_library.py')],cwd=ROOT,check=True)
library_folder=ROOT/'work/espnow-native-library'/library_version/'sdk'
archive=library_folder/'lib/libxnow.a'
library_report=json.loads((library_folder/'build.json').read_text())
if hashlib.sha256(archive.read_bytes()).hexdigest()!=library_report['archive_sha256']:raise ValueError('library manifest mismatch')
sources=['runtime/apps/espnow-chat/chat_app.c','runtime/apps/espnow-chat/chat_keyboard.c','runtime/apps/espnow-chat/chat_client.c',
         'runtime/apps/espnow-chat/chat_handoff.c','runtime/platform/espnow/xnow_managed_process.c',
         'runtime/native/frontend.c','runtime/native/linux_devices.c',
         'runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c',
         'runtime/store/start.c','runtime/store/start.S']
folder=OUT/'HOMEBREW/apps/espnow-chat';folder.mkdir(parents=True,exist_ok=True)
worker=folder/'radio-worker'
subprocess.run([sys.executable,str(ROOT/'runtime/platform/espnow/build_exchange_lab.py')],cwd=ROOT,check=True)
owner_sources=['runtime/apps/espnow-chat/chat_owner.c','runtime/apps/espnow-chat/chat_owner_platform.c','runtime/apps/espnow-chat/chat_handoff.c','runtime/apps/espnow-chat/chat_handoff_owner.c','runtime/platform/espnow/xnow_managed_process.c','runtime/store/start.c','runtime/store/start.S']
owner_sources+=['runtime/platform/espnow/xnow_handoff.c','runtime/native/app_process.c','runtime/native/linux_process_posix.c']
owner_flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
    '-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie',
    '-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
    '-I'+str(ROOT/'sdk/include'),'-I'+str(ROOT/'work/espnow-stock-reload-lab'),'-I'+str(ROOT/'work/espnow-exchange-lab')]
sdk_run(['arm-linux-gnueabi-gcc',*owner_flags,*owner_sources,str(archive),str(ROOT/'work/stock-resolver-probe/libcnmgr.so.1'),
    '-Wl,--no-as-needed',str(ROOT/'work/stock-resolver-probe/libpthread.so.0'),str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(worker)],cwd=ROOT,check=True)
worker_sha=hashlib.sha256(worker.read_bytes()).hexdigest()
(OUT/'chat_worker_identity.h').write_text('#define CHAT_WORKER_BYTES '+str(worker.stat().st_size)+'u\nstatic const unsigned char chat_worker_sha[32]={'+','.join(str(b) for b in bytes.fromhex(worker_sha))+'};\n')
owner_base=['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',str(LIB)+':'+str(ROOT/'work/stock-resolver-probe'),str(worker)]
subprocess.run(owner_base+['--help'],check=True,timeout=15)
app=folder/'app';objects=[]
for i,source in enumerate(sources):
    obj=OUT/f'{i}.o'
    sdk_run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                    '-ffunction-sections','-fdata-sections',
                    '-DHB_USE_POSIX_DEVICE_IO','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                    '-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin',
                    '-fno-pie','-fno-stack-protector','-I'+str(ROOT/'work/espnow-radio-bridge'),'-I'+str(ROOT/'sdk/include'),'-I'+str(OUT),
                    '-MMD','-MF',str(OUT/f'{i}.d'),'-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
sdk_run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none',
                '-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,str(archive),str(LIB/'libc.so.6'),
                str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',str(LIB),str(app)]
checks=[]
for arg in ['--help','--version','--selftest']:
    r=subprocess.run(base+[arg],capture_output=True,text=True,timeout=15);assert r.returncode==0,(r.stdout,r.stderr)
    checks.append({'arg':arg,'stdout':r.stdout})
from PIL import Image
for flag,name in [('--render-preview','preview'),('--render-keyboard-preview','keyboard-preview')]:
    r=subprocess.run(base+[flag],capture_output=True,timeout=15);assert r.returncode==0 and len(r.stdout)==240*432*2
    (OUT/(name+'.rgb565')).write_bytes(r.stdout);rgb=bytearray()
    for i in range(0,len(r.stdout),2):
        v=r.stdout[i]|(r.stdout[i+1]<<8);rgb.extend((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
    Image.frombytes('RGB',(240,432),bytes(rgb)).save(OUT/(name+'.png'))
version=(ROOT/'runtime/apps/espnow-chat/VERSION').read_text().strip();data=app.read_bytes();digest=hashlib.sha256(data).hexdigest()
(folder/'app.ini').write_text(f'api=1\nid=espnow-chat\nname=ESP-NOW Chat\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={digest}\n')
(folder/'launch.contract').write_text('XNOW-MANAGED-1\n'+digest+'\n')
(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.name}\n' for p in sorted([app,worker,folder/'app.ini',folder/'launch.contract'])))
with app.open('rb') as f:
    e=ELFFile(f);needed=[t.needed for t in e.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED'];assert needed==['libc.so.6']
import shlex
dependencies=set(sources)
for i in range(len(sources)):
    rule=(OUT/f'{i}.d').read_text().replace('\\\n',' ').split(':',1)[1]
    for name in shlex.split(rule):
        path=(ROOT/name).resolve()
        if path.is_relative_to(ROOT.resolve()):dependencies.add(path.relative_to(ROOT.resolve()).as_posix())
report={'built':True,'version':version,'bytes':len(data),'sha256':digest,'needed':needed,'checks':checks,
        'radio_owner_sha256':worker_sha,'radio_owner_bytes':worker.stat().st_size,'owner_sources':{x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in owner_sources},'linked_library_version':library_version,'linked_library_sha256':library_report['archive_sha256'],
        'linked_library_sources':library_report['source_hashes'],
        'renderer_preview':True,'hardware_tested':False,'device_written':False,'radio_installed':False,
        'managed_launcher_required':True,'deployable':False,'pending_validation':['physical graphical UI through managed launcher','physical APF/USB/sleep and stock network restoration'],
        'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sorted(dependencies)}}
(OUT/'build.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','linked_library_sources')},indent=2))
