"""Owned URL/DNS/TCP/TLS/cache task against explicit local fixtures only."""
from pathlib import Path
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from elftools.elf.elffile import ELFFile
from sdk_bootstrap import SERVICE_LIBRARIES
from sdk_build import stock_runtime

ROOT = Path(__file__).resolve().parents[1]
TLS = ROOT / 'work/external-tls-probe'
CRYPTO = TLS / 'bearssl-0.6'
RESOLVER = ROOT / 'work/stock-resolver-probe'
BEARSSL = TLS / 'arm-build/libbearssl.a'

MODULES = ['download_task','download_plan','inventory','package','cleanup_plan','resolver','connect_step','https_url','https_fetch','tls_socket_step','socket_step','deadline','tls_platform','download_file','download_stream','http_response','stock_fs_bridge','stock_stat64','stock_tls_compat']
TASK_SOURCES = ['runtime/store/'+name+'.c' for name in MODULES]+['runtime/native/sha256.c','runtime/native/syscalls.S','tools/test_download_task.c','tools/download_file_faults.c','tools/stock_test_start.c','tools/store_link_start.S']


def prepare_task_fixture(work):
    lib = stock_runtime()
    pinned = {
        RESOLVER / 'libcares.so.2': SERVICE_LIBRARIES['libcares.so.2'],
        RESOLVER / 'ares.h': 'ed0804876d9dc6846acd30165ccc5a866cd7e6987aa5907adb53130dc3868f04',
        ROOT / 'work/bearssl-0.6.tar.gz': '6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14',
    }
    for path, digest in pinned.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Missing or mismatched SDK input {path}; run tools/sdk.py setup --services')
    if not BEARSSL.is_file():
        raise ValueError('ARM BearSSL archive missing; run tools/sdk.py setup --services')
    with tarfile.open(ROOT / 'work/bearssl-0.6.tar.gz') as archive:
        sample = archive.extractfile('bearssl-0.6/samples/client_basic.c').read().decode()
    start = sample.index('static const unsigned char TA0_DN')
    end = sample.index('\n', sample.index('#define TAs_NUM'))
    (work / 'fixture_ta.h').write_text(sample[:sample.index('#include')] + sample[start:end] + '\n')
    return lib


def main():
    work = ROOT / 'work/download-task-tests'
    work.mkdir(exist_ok=True)
    lib = prepare_task_fixture(work)
    sources = TASK_SOURCES
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(RESOLVER),'-I'+str(CRYPTO/'inc'),'-I'+str(CRYPTO/'samples'),'-I'+str(RESOLVER),'-I'+str(work),*sources,str(BEARSSL),str(RESOLVER/'libcares.so.2'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
    with tempfile.TemporaryDirectory(prefix='task-cache-',dir=work) as cache:
     run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{RESOLVER}',str(work/'test.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_TASK_CACHE=cache))
     assert run.returncode==0,(run.returncode,run.stdout,run.stderr[-10000:])
     assert not list(Path(cache).iterdir())
    families=re.findall(r'\bsocket\(([^,\n]+)',run.stderr.lower());assert families and all(f.strip() in ('pf_inet','af_inet') for f in families)
    operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
    assert operations and all('127.0.0.1' in line or '127.0.0.2' in line for line in operations),operations
    elf=ELFFile(io.BytesIO((work/'test.arm').read_bytes()));workspace=next(s['st_size'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name=='task')
    report={'all_bounded_checks_passed':True,'physical_device_access':False,'runtime_output':run.stdout.splitlines(),'scenarios':9,'cases':['full DNS/TCP/TLS/HTTP/READY','NXDOMAIN','silent DNS deadline','wrong trust root','cancel pending DNS','HTTP hash mismatch','fsync error plus explicit cache recheck','pre-cancel before task I/O','first address refusal then second address success'],'workspace_reused_after_discard':True,'workspace_bytes_excluding_stack_library_heap':workspace,'owned_crypto_buffers_zero_checked':True,'cache_empty_after_explicit_discard':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'trace':run.stderr,'loopback_operations':operations,'limits':['Only local DNS/TCP endpoints127.0.0.1 and refused127.0.0.2; no system/default/external DNS or network.','Sample trust roots/key, host entropy/clock, original c-ares/libc under QEMU; no device/Wi-Fi qualification.','No redirects, package publication, UI integration or runtime memory budget qualification.','Fault wrappers only in test; context reuse requires explicit discard and no owned resources.']}
    report['linked_input_hashes']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (BEARSSL,RESOLVER/'libcares.so.2',lib/'libc.so.6',lib/'ld-linux.so.3')}
    (ROOT/'sources/native-download-task-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(run.stdout.strip());print('Task workspace bytes:',workspace)


if __name__ == '__main__':
    main()
