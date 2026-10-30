"""Build local experimental ARM library; no deployment, device or network IO."""
from pathlib import Path
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from marvell_firmware import parse
SOURCE=ROOT/'runtime/platform/espnow'
version=(SOURCE/'VERSION').read_text().strip()
if not re.fullmatch(r'\d+\.\d+\.\d+-dev\.\d+',version):raise ValueError('invalid experimental VERSION')
OUT=ROOT/'work/espnow-native-library'/version;SDK=OUT/'sdk'
for name in ('include','lib','examples'):(SDK/name).mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
libs={LIB/'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
      LIB/'ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
      STOCK/'libcnmgr.so.1':'688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1',
      RESOLVER/'libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474'}
for path,digest in libs.items():
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('unqualified library '+path.name)
radio=ROOT/'work/espnow-radio-bridge/bridge.elf'
candidate=ROOT/'work/espnow-radio-candidate-poll-filter'
review=json.loads((candidate/'review.json').read_text());blob=(candidate/'candidate/sd8686.bin').read_bytes()
if hashlib.sha256(blob).hexdigest()!=review['candidate_sha256']:raise ValueError('candidate/report mismatch')
memory={r.address+i:b for r in parse(blob) if r.command==1 for i,b in enumerate(r.data)}
with radio.open('rb') as f:
    elf=ELFFile(f)
    for name in ('.text','.state'):
        section=elf.get_section_by_name(name);base=section['sh_addr']
        if bytes(memory[base+i] for i in range(section['sh_size']))!=section.data():raise ValueError('candidate/payload mismatch')
    code=elf.get_section_by_name('.text');state=elf.get_section_by_name('.state')
    guard=(ROOT/'work/espnow-radio-bridge/xnow_radio_build.h').read_text()
    encoded=re.search(r'xnow_radio_expected_code\[\]=\{([0-9,]+)\};',guard)
    if not encoded or bytes(map(int,encoded[1].split(',')))!=code.data():raise ValueError('stale radio guard bytes')
    for macro,expected in (('CODE',code['sh_addr']),('STATE',state['sh_addr'])):
        match=re.search(r'#define XNOW_RADIO_'+macro+r'_BASE (0x[0-9a-f]+)u',guard)
        if not match or int(match[1],16)!=expected:raise ValueError('stale radio guard address')
sources=([f'runtime/platform/espnow/{name}.c' for name in
         ('xnow_version','xnow_wire','xnow_chat','xnow_mailbox','xnow_sd8686','xnow_session','xnow_manager',
          'xnow_loader_job','xnow_rf_init','xnow_file_check','xnow_control','xnow_ipc_guard')]+
        ['runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c'])
# Full native implementation is included so copied public headers never
# advertise missing archive symbols. BearSSL remains a separately linked dep.
crypto=ROOT/'work/external-tls-probe/bearssl-0.6';crypto_archive=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
if hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()!='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14':raise ValueError('unqualified crypto source')
if not crypto_archive.is_file():raise ValueError('Run SDK setup --services for BearSSL')
sources += ['runtime/platform/espnow/'+name+'.c' for name in ('xnow_peer','xnow_full','xnow_endpoint','xnow_pn','xnow_pn_file','xnow_ccmp','xnow_security','xnow_endpoint_security','xnow_keywrap','xnow_keyring','xnow_full_guard','xnow_sd8686_full','xnow_full_control')]
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC',
       '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DXNOW_LIBRARY_VERSION='+json.dumps(version),
       '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
       '-I'+str(ROOT/'work/espnow-radio-bridge'),'-I'+str(crypto/'inc')]
objects=[];dependencies=set(sources)
for index,source in enumerate(sources):
    obj=OUT/f'{index}.o';dep=OUT/f'{index}.d'
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-MMD','-MF',str(dep),'-c',source,'-o',str(obj)],cwd=ROOT,check=True)
    objects.append(str(obj))
    for name in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
        path=(ROOT/name).resolve()
        if path.is_relative_to(ROOT.resolve()):dependencies.add(path.relative_to(ROOT.resolve()).as_posix())
archive=SDK/'lib/libxnow.a'
# Replacing only this builder's generated archive avoids retaining stale members.
if archive.exists():archive.unlink()
subprocess.run(['arm-linux-gnueabi-ar','rcsD',str(archive),*objects],check=True)
# Export only headers actually used by compiled archive sources; private
# research prototypes must not advertise symbols absent from this version.
headers=sorted(p for p in SOURCE.glob('xnow*.h') if p.name=='xnow.h' or p.relative_to(ROOT).as_posix() in dependencies)
allowed_headers={p.name for p in headers}
for stale in (SDK/'include').glob('*.h'):
    if stale.name not in allowed_headers:
        if stale.is_symlink() or not stale.resolve().is_relative_to((SDK/'include').resolve()):raise ValueError('Unexpected generated header path')
        stale.unlink()
for path in headers:
    shutil.copy2(path,SDK/'include'/path.name);dependencies.add(path.relative_to(ROOT).as_posix())
consumer=ROOT/'tools/fixtures/xnow_library_consumer.c'
shutil.copy2(consumer,SDK/'examples/no_device_smoke.c');shutil.copy2(SOURCE/'LIBRARY.md',SDK/'README.md')
shutil.copy2(SOURCE/'VALIDATION.md',SDK/'VALIDATION.md')
dependencies.add(consumer.relative_to(ROOT).as_posix())
dependencies.update(('runtime/platform/espnow/VERSION','runtime/platform/espnow/LIBRARY.md','runtime/platform/espnow/VALIDATION.md',
                     'runtime/platform/espnow/build_library.py'))
startup=[]
for index,name in enumerate(('runtime/store/start.c','runtime/store/start.S')):
    obj=OUT/f'start-{index}.o';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',name,'-o',str(obj)],cwd=ROOT,check=True);startup.append(str(obj));dependencies.add(name)
test=OUT/'consumer.o';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-I'+str(SDK/'include'),'-c',str(consumer),'-o',str(test)],cwd=ROOT,check=True)
checks=[]
for whole in (False,True):
    app=OUT/('whole-library.arm' if whole else 'consumer.arm')
    archives=['-Wl,--whole-archive',str(archive),'-Wl,--no-whole-archive'] if whole else [str(archive)]
    external=[str(crypto_archive),str(STOCK/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0')] if whole else []
    subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none',
                    '-Wl,--dynamic-linker=/lib/ld-linux.so.3',*startup,str(test),*archives,*external,
                    str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],check=True)
    run=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',f'{LIB}:{STOCK}:{RESOLVER}',str(app)],
                       capture_output=True,text=True,timeout=15,check=True)
    checks.append({'whole_archive_link':whole,'stdout':run.stdout,'sha256':hashlib.sha256(app.read_bytes()).hexdigest()})
# C++ consumes public headers and links C-compiled core objects, without vendor IO.
host_objects=[]
for index,name in enumerate(('xnow_version','xnow_wire','xnow_chat','xnow_session')):
    obj=OUT/f'host-{index}.o';subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',
        '-DXNOW_LIBRARY_VERSION='+json.dumps(version),'-c',str(SOURCE/(name+'.c')),'-o',str(obj)],check=True);host_objects.append(str(obj))
cpp=OUT/'cpp-consumer.o'
subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(SDK/'include'),'-x','c++','-c',str(consumer),'-o',str(cpp)],check=True)
subprocess.run(['g++',str(cpp),*host_objects,'-o',str(OUT/'cpp-consumer')],check=True)
cpp_run=subprocess.run([str(OUT/'cpp-consumer')],capture_output=True,text=True,check=True)
report={'built':True,'version':version,'target':'Japanese X1000 JP1.11 ARMv5TE soft-float Sony-libc profile',
        'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_bytes':archive.stat().st_size,
        'radio_candidate_sha256':review['candidate_sha256'],'radio_payload_sha256':hashlib.sha256(radio.read_bytes()).hexdigest(),
        'abi_library_hashes':{p.relative_to(ROOT).as_posix():digest for p,digest in libs.items()},
        'compiler':subprocess.check_output(['arm-linux-gnueabi-gcc','--version'],text=True).splitlines()[0],
        'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sorted(dependencies)},
        'arm_qemu_consumer_checks':checks,'host_cpp_link_check':cpp_run.stdout,'arm_cpp_tested':False,
        'bearssl_archive_sha256':hashlib.sha256(crypto_archive.read_bytes()).hexdigest(),'sony_libraries_distributed':False,'hardware_qualified':False,'device_written':False}
(SDK/'build.json').write_text(json.dumps(report,indent=2))
package=OUT/('XNOW-'+version+'-experimental-sdk.zip')
files=[*(SDK/'include').glob('*.h'),archive,SDK/'examples/no_device_smoke.c',SDK/'README.md',SDK/'VALIDATION.md',SDK/'build.json']
with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as zipout:
    for path in sorted(files):zipout.write(path,path.relative_to(SDK).as_posix())
(OUT/'package.json').write_text(json.dumps({'file':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
    'files':[p.relative_to(SDK).as_posix() for p in sorted(files)],'published':False,'sony_binaries_included':False},indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
