"""Build stock-manager Wi-Fi helper locally; never requests network or login."""
from pathlib import Path
import hashlib,io,json,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-wifi';work.mkdir(exist_ok=True)
archive=ROOT/'work/upg-jp/verified-3.bin';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(archive) as t:data=t.extractfile('./usr/lib/libcnmgr.so.1.0').read()
elf=ELFFile(io.BytesIO(data));assert next(tag.soname for tag in elf.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_SONAME')=='libcnmgr.so.1'
(work/'libcnmgr.so.1').write_bytes(data)
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe'
sources=['runtime/apps/qqmusic/qqmusic_wifi_helper.c','runtime/apps/qqmusic/qqmusic_wifi_link.c','runtime/native/linux_signals.c','runtime/native/syscalls.S','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,--disable-new-dtags,-rpath,$ORIGIN/lib',*sources,str(work/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(resolver/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'wifi-helper')],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{work}',str(work/'wifi-helper'),'--help'],check=True,timeout=10)
report={'built':True,'physical_device_tested':False,'network_requested':False,'ready_to_deploy':False,'standalone_help_only':True,'helper_sha256':hashlib.sha256((work/'wifi-helper').read_bytes()).hexdigest(),'stock_library_sha256':hashlib.sha256(data).hexdigest(),'sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/apps/qqmusic/qqmusic_wifi.h']},'policy':'Only original connection manager; RAM-backed IPC guard; no QQ account or persisted diagnostics.','limits':['Original client-library handle use across fork and concurrent request/cancel transport are not qualified by help execution.','Physical network ownership, blocked-IO shutdown and real driver timing remain unverified.','Local native source is bound; this helper build alone is not physical deployment acceptance.']}
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
