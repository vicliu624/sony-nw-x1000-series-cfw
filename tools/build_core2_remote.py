"""Build/review the Core2 controller without serial access or flashing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from app_registry import ROOT


def build(platformio, packages_directory=None):
    if not platformio.is_file():
        raise FileNotFoundError("PlatformIO executable not found: " + str(platformio))
    project=ROOT/'runtime/apps/wireless-remote/core2';work=ROOT/'work/core2-remote-build'
    work.mkdir(parents=True,exist_ok=True);pio=platformio
    log=work.parent/'core2-remote-build.log'
    packages_directory=(packages_directory or ROOT/'work/core2-platformio-packages').resolve()
    if not packages_directory.is_relative_to((ROOT/'work').resolve()) or packages_directory==(ROOT/'work').resolve():
     raise ValueError('Use a dedicated package directory under work/')
    packages_directory.mkdir(parents=True,exist_ok=True)
    environment=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
                     PLATFORMIO_PACKAGES_DIR=str(packages_directory))
    with log.open('w',encoding='utf-8') as output:
     result=subprocess.run([str(pio),'run','-d',str(project)],cwd=ROOT,
                           env=environment,stdout=output,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(log.read_text(encoding='utf-8',errors='replace')[-5000:])
    folder=work/'walkman-core2';artifacts={}
    for name in ('firmware.bin','bootloader.bin','partitions.bin'):
     p=folder/name;data=p.read_bytes();artifacts[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    inputs=[p for p in project.rglob('*') if p.is_file() and '.pio' not in p.parts
            and p != project/'src/idf_component.yml.orig']
    inputs += [ROOT/'runtime/apps/wireless-remote'/n for n in ('mode_wire.c','mode_wire.h','link.c','link.h','control.c','control.h','status_auth.c','status_auth.h','session_wire.c','session_wire.h','receiver.c','receiver.h','library_wire.c','library_wire.h','library_client.c','library_client.h')]
    inputs += [ROOT/'runtime/native/sha256.c',ROOT/'runtime/native/sha256.h',Path(__file__)]
    inputs += [ROOT/'runtime/apps/wireless-remote'/n for n in ('pairing_proof.c','pairing_proof.h')]
    inputs += [ROOT/'runtime/apps/wireless-remote'/n for n in ('pairing_auto.c','pairing_auto.h','pairing_curve.c')]
    inputs += [ROOT/'runtime/apps/wireless-remote/transport_goal.h']
    inputs += [ROOT/'runtime/apps/wireless-remote/playback_icon.h',ROOT/'runtime/apps/wireless-remote/on_demand_link.h']
    inputs += [ROOT/'runtime/apps/wireless-remote'/n for n in ('artwork_wire.c','artwork_wire.h','artwork_client.c','artwork_client.h','artwork_image.c','artwork_image.h')]
    inputs += [ROOT/'runtime/platform/player/artwork.h']
    inputs += [ROOT/'runtime/platform/espnow'/name for name in ('xnow_link.c','xnow_link.h')]
    report=dict(built=True,version=(project/'VERSION').read_text().strip(),target='Core2 + Faces Gamepad3',
                artifacts=artifacts,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                device_accessed=False,flashed=False,hardware_qualified=False,
                limitations=['Library protocol/UI integrated; actual native library/playlist/queue provider capabilities require physical acceptance','Five modes implemented but not physically accepted','Core2 display/touch/Gamepad unqualified'])
    report['packages_directory']=packages_directory.relative_to(ROOT).as_posix()
    destination=ROOT/'work/core2-remote-reviews'/str(time.time_ns());destination.mkdir(parents=True)
    for name,row in artifacts.items():
     target=destination/name;shutil.copy2(folder/name,target)
     if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Core2 review artifact changed during snapshot')
     row['local']=target.relative_to(ROOT).as_posix()
    (destination/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(built=True,version=report['version'],review=destination.relative_to(ROOT).as_posix(),artifacts=artifacts,flashed=False),indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--platformio', type=Path,
        default=Path.home() / '.platformio/penv/Scripts/pio.exe',
        help='Explicit PlatformIO executable; the supported local profile uses Windows PlatformIO',
    )
    parser.add_argument('--packages-directory',type=Path,
                        help='Dedicated PlatformIO package cache under work/, leaving other projects packages intact')
    args = parser.parse_args()
    build(args.platformio.resolve(),args.packages_directory)


if __name__ == '__main__':
    main()
