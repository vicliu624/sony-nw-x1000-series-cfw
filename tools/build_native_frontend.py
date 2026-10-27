"""Build only ordinary host tests and external ARM executable; never UPG or a device."""
from pathlib import Path
import argparse,subprocess,json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
def run(*args):subprocess.run(args,cwd=ROOT,check=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-output',help='Separate build directory under work/; does not replace the existing candidate/build manifest');options=parser.parse_args()
    area=None
    if options.review_output:
        area=(ROOT/options.review_output).resolve();assert area.is_relative_to(ROOT/'work') and area!=ROOT/'work'
        version_text=(ROOT/'VERSION').read_text().strip()
        for prefix in ('integration-','product-review-','network-external-'):
            reserved=ROOT/'work'/(prefix+version_text)
            assert not area.is_relative_to(reserved),'Review build must not write inside a pinned candidate'
        area.mkdir(parents=True,exist_ok=True)
    run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','runtime/native/frontend.c','tools/test_native_frontend.c','-o','work/test-native-frontend')
    run('./work/test-native-frontend')
    run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','runtime/native/sony_bridge.c','tools/test_sony_bridge.c','-o','work/test-sony-bridge')
    run('./work/test-sony-bridge')
    process_test=str((area or ROOT/'work')/'test-app-process')
    run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','runtime/native/app_process.c','tools/test_app_process.c','-o',process_test)
    run(process_test)
    devices_test=str((area or ROOT/'work')/'test-linux-devices')
    run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','runtime/native/linux_devices.c','tools/test_linux_devices.c','-o',devices_test)
    run(devices_test)
    files_test=str((area or ROOT/'work')/'test-linux-files')
    run('gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','runtime/native/linux_files.c','tools/test_linux_files.c','-o',files_test)
    run(files_test)
    version=(ROOT/'VERSION').read_text().strip()
    assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',version)
    flags=['-DHB_BUILD_VERSION="'+version+'"','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-Wall','-Wextra','-Werror','-nostdlib','-static','-Wl,-e,_start','-Wl,--build-id=none']
    files=['frontend.c','sony_bridge.c','sha256.c','support.c','selftest.c','platform_arm.c','app_process.c','home_key.c','linux_process.c','linux_devices.c','app_catalog.c','linux_files.c','linux_signals.c','entry_start.S','syscalls.S']
    artifact=(area/'launcher.elf') if area else ROOT/'work/x1000-homebrew-frontend'
    object_area=(area/'objects') if area else ROOT/'work/native-frontend-objects'
    object_area.mkdir(parents=True,exist_ok=True)
    compile_flags=[flag for flag in flags if not flag.startswith('-Wl,')]
    objects=[]
    for index,name in enumerate(files):
        obj=object_area/(str(index).zfill(2)+'-'+Path(name).stem+'.o')
        run('arm-linux-gnueabi-gcc',*compile_flags,'-c','runtime/native/'+name,'-o',str(obj));objects.append(str(obj))
    run('arm-linux-gnueabi-gcc',*flags,*objects,'-lgcc','-o',str(artifact))
    run('qemu-arm','-cpu','arm926',str(artifact),'--selftest')
    b=artifact.read_bytes();result={'version':version,'artifact':str(artifact.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'scope':'experimental external ARM executable, no Sony UI hook or hardware qualification','firmware_created':False}
    result['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'VERSION',ROOT/'tools/test_app_process.c',ROOT/'tools/test_linux_devices.c',ROOT/'tools/test_linux_files.c',*[ROOT/'runtime/native'/f for f in files],ROOT/'runtime/native/app_process.h',ROOT/'runtime/native/linux_process.h',ROOT/'runtime/native/linux_devices.h',ROOT/'runtime/native/linux_device_io.h',ROOT/'runtime/native/app_catalog.h',ROOT/'runtime/native/linux_files.h',ROOT/'runtime/native/linux_signals.h',ROOT/'runtime/native/font.inc']}
    result['review_only']=bool(area)
    result['profile']='platform-interfaces-refactor-review' if area else 'external-frontend-build'
    (area/'build.json' if area else ROOT/'work/native-frontend-build.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()

