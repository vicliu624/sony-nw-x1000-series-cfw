"""SDK host/ARM regression and clean-source starter checks. No physical device."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from app_registry import ROOT
from sdk_build import COMMON,NATIVE

def run(command,**kwargs):
    result=subprocess.run(list(map(str,command)),cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=90,**kwargs)
    if result.returncode:raise RuntimeError(' '.join(map(str,command))+'\n'+result.stdout+result.stderr)
    return result.stdout

def main():
    if sys.flags.optimize:raise RuntimeError('Do not disable assertions')
    work=ROOT/'work/sdk-tests'/str(time.time_ns());work.mkdir(parents=True)
    flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-I'+str(ROOT/'sdk/include')]
    common=[ROOT/p for p in COMMON if not p.endswith('entry.c')]
    fixture=ROOT/'sdk/tests/runtime.c'
    host=work/'runtime-host';data=work/'data';data.mkdir()
    run(['gcc',*flags,'-DXW_HOST',fixture,*common,'-o',host]);host_result=run([host,data]);print(host_result.strip())
    if os.environ.get('GITHUB_ACTIONS') and 'SKIP' in host_result:raise RuntimeError('CI must exercise the complete Linux filesystem fixture')
    lib=ROOT/'work/arm-signal-tests/lib';arm=work/'runtime-arm'
    run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-fno-stack-protector','-DHB_STORE_SONY_LIBC','-DHB_USE_POSIX_DEVICE_IO',
         fixture,*common,*[ROOT/p for p in NATIVE],'-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',lib/'libc.so.6',lib/'ld-linux.so.3','-lgcc','-o',arm])
    print(run(['qemu-arm','-cpu','arm926',lib/'ld-linux.so.3','--library-path',lib,arm]).strip())
    # End-to-end real maintained SDK apps, actual host rendering and ARM packaging.
    from sdk_build import compile_app
    from build_app import package
    from verify_app_package import verify
    reports=[]
    for ident in ('sdk-counter','sdk-canvas'):
        definition=ROOT/'runtime/apps'/ident
        host=compile_app(definition,work/ident/'host',host=True)
        folder=work/ident/'host-data';folder.mkdir()
        script=work/ident/'events.txt';script.write_text('tap 60 215\ntick 32\n')
        frame=work/ident/'frame.ppm'
        run([host,'--render',frame,'--events',script,'--data',folder])
        from PIL import Image
        with Image.open(frame) as image:assert image.size==(240,432)
        if ident=='sdk-counter':assert (folder/'counter.bin').read_bytes()==b'\x01\0\0\0'
        build=work/ident/'arm';compile_app(definition,build)
        finished=package(ident,build,work/ident/'package');reports.append(verify(finished))
        # The same generated package rejects an edited executable.
        app=finished/'app';original=app.read_bytes();app.write_bytes(original+b'changed')
        try:verify(finished)
        except ValueError:pass
        else:raise AssertionError('Changed executable accepted')
        app.write_bytes(original)
    discovery=work/'discovery-arm'
    run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-fno-stack-protector',
         ROOT/'sdk/tests/discovery.c',*[ROOT/p for p in ('runtime/native/app_catalog.c','runtime/native/linux_files.c','runtime/native/sha256.c',
         'runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S')],
         '-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',lib/'libc.so.6',lib/'ld-linux.so.3','-lgcc','-o',discovery])
    apps=work/'discovery-apps';apps.mkdir();shutil.copytree(work/'sdk-counter/package',apps/'sdk-counter')
    print(run(['qemu-arm','-cpu','arm926',lib/'ld-linux.so.3','--library-path',lib,discovery,apps]).strip())
    report={'passed':True,'apps':reports,'host_runtime':True,'host_fifo_test_skipped':'SKIP FIFO' in host_result,'original_loader_arm_runtime':True,'host_render_and_persistence':True,
            'native_unknown_id_discovery':True,'hardware_accessed':False,'firmware_created':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'runtime/platform/sdk').glob('*')) if p.is_file()}}
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
