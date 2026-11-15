"""Build local experimental ARM library; no deployment, device or network IO."""
import argparse
from pathlib import Path
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_espnow_radio_candidate import HELPER_SHA, construct
from component_receipts import digest, private
from sdk_build import fresh_work

SOURCE = ROOT / 'runtime/platform/espnow'
LEGACY_REVIEW = ROOT / 'work/espnow-radio-candidate-poll-filter/review.json'


def build_sdk(output=None, *, package=False, mailbox_review=None):
    version = (SOURCE / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+-dev\.\d+', version):
        raise ValueError('invalid experimental VERSION')
    out = fresh_work(output or ROOT / 'work/espnow-native-library' / ('build-' + str(time.time_ns())))
    with tempfile.TemporaryDirectory(prefix='compiler-', dir=out) as folder:
        scratch = Path(folder)
        report = compile_sdk(scratch, version, mailbox_review=mailbox_review)
        sdk = out / 'sdk'
        (scratch / 'sdk').rename(sdk)
    if package:
        package_sdk(out, sdk, version)
    return sdk / 'build.json', report


def mailbox_inputs(review_path, scratch):
    legacy = review_path is None
    review_path = private(LEGACY_REVIEW if legacy else review_path)
    folder = review_path.parent
    review = json.loads(review_path.read_text(encoding='utf-8'))
    radio = private(ROOT/'work/espnow-radio-bridge/bridge.elf' if legacy else folder/'bridge.elf')
    candidate = private(folder/'candidate/sd8686.bin')
    stock = private(folder/'stock/sd8686.bin')
    helper = private(folder/'candidate/helper_sd.bin')
    image, reconstructed = construct(stock.read_bytes(), radio)
    if image != candidate.read_bytes() or reconstructed['candidate_sha256'] != review['candidate_sha256']:
        raise ValueError('Mailbox image differs from the reviewed stock image and payload')
    if not legacy and reconstructed != review:
        raise ValueError('Mailbox review differs from the reconstructed image')
    if digest(helper) != HELPER_SHA:
        raise ValueError('Mailbox helper differs from the pinned Sony image')
    payload = radio.read_bytes()
    if hashlib.sha256(payload).hexdigest() != reconstructed['payload_elf_sha256']:
        raise ValueError('Mailbox payload changed during validation')
    with io.BytesIO(payload) as stream:
        elf = ELFFile(stream)
        code = elf.get_section_by_name('.text')
        guard = ('#ifndef XNOW_RADIO_BUILD_H\n#define XNOW_RADIO_BUILD_H\n'
                 f'#define XNOW_RADIO_CODE_BASE 0x{code["sh_addr"]:08x}u\n'
                 f'#define XNOW_RADIO_STATE_BASE {reconstructed["mailbox_address"]}u\n'
                 'static const unsigned char xnow_radio_expected_code[]={' +
                 ','.join(str(value) for value in code.data()) + '};\n#endif\n')
    (scratch/'xnow_radio_build.h').write_text(guard, encoding='utf-8')
    return review_path, reconstructed, (radio, candidate, stock, helper, review_path)


def compile_sdk(scratch, version, *, mailbox_review=None):
    SDK = scratch / 'sdk'
    for name in ('include', 'lib', 'examples'):
        (SDK / name).mkdir(parents=True)
    LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
    libs={LIB/'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
          LIB/'ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
          STOCK/'libcnmgr.so.1':'688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1',
          RESOLVER/'libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474'}
    for path,digest in libs.items():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('unqualified library '+path.name)
    mailbox_path, review, mailbox_files = mailbox_inputs(mailbox_review, scratch)
    sources=([f'runtime/platform/espnow/{name}.c' for name in
             ('xnow_version','xnow_wire','xnow_chat','xnow_mailbox','xnow_sd8686','xnow_session','xnow_manager',
              'xnow_loader_job','xnow_rf_init','xnow_file_check','xnow_control','xnow_ipc_guard')]+
            ['runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c'])
    # Full native implementation is included so copied public headers never
    # advertise missing archive symbols. BearSSL remains a separately linked dep.
    crypto=ROOT/'work/external-tls-probe/bearssl-0.6';crypto_archive=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
    if hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()!='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14':raise ValueError('unqualified crypto source')
    if not crypto_archive.is_file():raise ValueError('Run SDK setup --services for BearSSL')
    sources += ['runtime/platform/espnow/'+name+'.c' for name in ('xnow_peer','xnow_full','xnow_endpoint','xnow_pn','xnow_pn_file','xnow_ccmp','xnow_security','xnow_endpoint_security','xnow_keywrap','xnow_keyring','xnow_full_guard','xnow_sd8686_full','xnow_sd8686_frames','xnow_full_control','xnow_shared_session','xnow_link','xnow_link_counter','xnow_owner_link')]
    flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC',
           '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DXNOW_LIBRARY_VERSION='+json.dumps(version),
           '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
           '-I'+str(scratch),'-I'+str(crypto/'inc')]
    objects=[];dependencies=set(sources)
    dependencies.update(path.relative_to(ROOT).as_posix() for path in (
        *mailbox_files, ROOT/'work/bearssl-0.6.tar.gz'))
    dependencies.update(('tools/prepare_espnow_radio_candidate.py', 'tools/marvell_firmware.py'))
    for index,source in enumerate(sources):
        obj=scratch/f'{index}.o';dep=scratch/f'{index}.d'
        subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-MMD','-MF',str(dep),'-c',source,'-o',str(obj)],cwd=ROOT,check=True)
        objects.append(str(obj))
        for name in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
            path=(ROOT/name).resolve()
            if path.is_relative_to(ROOT) and not path.is_relative_to(scratch):
                dependencies.add(path.relative_to(ROOT).as_posix())
    archive=SDK/'lib/libxnow.a'
    subprocess.run(['arm-linux-gnueabi-ar','rcsD',str(archive),*objects],cwd=ROOT,check=True)
    # Export only headers actually used by compiled archive sources; private
    # research prototypes must not advertise symbols absent from this version.
    headers=sorted(p for p in SOURCE.glob('xnow*.h') if p.name!='xnow_shared_session.h' and
                   (p.name=='xnow.h' or p.relative_to(ROOT).as_posix() in dependencies))
    for path in headers:
        shutil.copy2(path,SDK/'include'/path.name);dependencies.add(path.relative_to(ROOT).as_posix())
    consumer=ROOT/'tools/fixtures/xnow_library_consumer.c'
    shutil.copy2(consumer,SDK/'examples/no_device_smoke.c')
    documentation = {}
    for source, name in (('LIBRARY.md', 'README.md'), ('VALIDATION.md', 'VALIDATION.md')):
        document = SDK / name
        shutil.copy2(SOURCE / source, document)
        documentation[name] = hashlib.sha256(document.read_bytes()).hexdigest()
    dependencies.add(consumer.relative_to(ROOT).as_posix())
    dependencies.update(('runtime/platform/espnow/VERSION', 'runtime/platform/espnow/build_library.py',
                         'tools/component_receipts.py'))
    startup=[]
    for index,name in enumerate(('runtime/store/start.c','runtime/store/start.S')):
        obj=scratch/f'start-{index}.o';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',name,'-o',str(obj)],cwd=ROOT,check=True);startup.append(str(obj));dependencies.add(name)
    test=scratch/'consumer.o';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-I'+str(SDK/'include'),'-c',str(consumer),'-o',str(test)],cwd=ROOT,check=True)
    checks=[]
    for whole in (False,True):
        app=scratch/('whole-library.arm' if whole else 'consumer.arm')
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
        obj=scratch/f'host-{index}.o';subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',
            '-DXNOW_LIBRARY_VERSION='+json.dumps(version),'-c',str(SOURCE/(name+'.c')),'-o',str(obj)],check=True);host_objects.append(str(obj))
    cpp=scratch/'cpp-consumer.o'
    subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(SDK/'include'),'-x','c++','-c',str(consumer),'-o',str(cpp)],check=True)
    subprocess.run(['g++',str(cpp),*host_objects,'-o',str(scratch/'cpp-consumer')],check=True)
    cpp_run=subprocess.run([str(scratch/'cpp-consumer')],capture_output=True,text=True,check=True)
    report={'built':True,'version':version,'target':'Japanese X1000 JP1.11 ARMv5TE soft-float Sony-libc profile',
            'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_bytes':archive.stat().st_size,
            'radio_candidate_sha256':review['candidate_sha256'],'radio_payload_sha256':review['payload_elf_sha256'],
            'mailbox_review':mailbox_path.relative_to(ROOT).as_posix(),
            'abi_library_hashes':{p.relative_to(ROOT).as_posix():digest for p,digest in libs.items()},
            'compiler':subprocess.check_output(['arm-linux-gnueabi-gcc','--version'],text=True).splitlines()[0],
            'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sorted(dependencies)},
            'documentation_sha256':documentation,
            'arm_qemu_consumer_checks':checks,'host_cpp_link_check':cpp_run.stdout,'arm_cpp_tested':False,
            'bearssl_archive_sha256':hashlib.sha256(crypto_archive.read_bytes()).hexdigest(),'sony_libraries_distributed':False,'hardware_qualified':False,'device_written':False}
    (SDK/'build.json').write_text(json.dumps(report,indent=2))
    return report


def package_sdk(OUT, SDK, version):
    archive = SDK / 'lib/libxnow.a'
    package=OUT/('XNOW-'+version+'-experimental-sdk.zip')
    build_receipt = SDK / 'build.json'
    documentation = json.loads(build_receipt.read_text())['documentation_sha256']
    documents = [SDK / name for name in ('README.md', 'VALIDATION.md')]
    for document in documents:
        if hashlib.sha256(document.read_bytes()).hexdigest() != documentation[document.name]:
            raise ValueError('SDK documentation differs from the staged build: ' + document.name)
    files=[*(SDK/'include').glob('*.h'), archive, SDK/'examples/no_device_smoke.c', *documents, build_receipt]
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED) as zipout:
        for path in sorted(files):zipout.write(path,path.relative_to(SDK).as_posix())
    (OUT/'package.json').write_text(json.dumps({'file':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
        'files':[p.relative_to(SDK).as_posix() for p in sorted(files)],'published':False,'sony_binaries_included':False},indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New directory under work/')
    parser.add_argument('--package', action='store_true', help='Also write a local SDK ZIP')
    parser.add_argument('--mailbox-review', type=Path, help='Select the mailbox radio review.json and its sibling inputs')
    args = parser.parse_args()
    path, report = build_sdk(args.output, package=args.package, mailbox_review=args.mailbox_review)
    print(json.dumps({'sdk_review': path.relative_to(ROOT).as_posix(),
                      **{key: value for key, value in report.items() if key != 'source_hashes'}}, indent=2))


if __name__ == '__main__':
    main()
