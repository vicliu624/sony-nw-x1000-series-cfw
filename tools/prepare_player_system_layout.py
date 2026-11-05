"""Prepare a single-player SDK root overlay for review; never creates a UPG."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time
from app_registry import ROOT
from build_player_host import build
from builtin_language import SETTINGS_SHA
from player_arm_guest import stock_libraries
from remote_choice_resource import SOURCE as REMOTE_TEMPLATE, TARGET as REMOTE_RESOURCE
sys.path.insert(0, str(ROOT/'scripts'))
from upg import unpack

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--localization-firmware', type=Path, required=True)
    parser.add_argument('--host-review',type=Path,help='Reuse a fresh composed managed host receipt instead of building the base profile')
    args=parser.parse_args()
    source=args.localization_firmware.resolve()
    if not source.is_relative_to(ROOT/'work'):
        raise ValueError('Use a local review input under work')
    _,parts=unpack(source.read_bytes(),require_stock=False)
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
        base=archive.extractfile('./usr/local/bin/SpiderApp').read()
        app_list=archive.extractfile('./etc/AppList.conf').read()
        resource_modes={m.name.removeprefix('./'):m.mode for m in archive.getmembers()
                        if m.isfile() and m.name.removeprefix('./').startswith('usr/local/share/gemini/res/')}
        archive_names={m.name.removeprefix('./').rstrip('/') for m in archive.getmembers()}
    if hashlib.sha256(base).hexdigest()!=SETTINGS_SHA:
        raise ValueError('Pinned built-in Settings base required')
    original=b'SpiderApp'
    wrapper_path='usr/local/bin/SpiderApp'
    payload_path='usr/local/lib/x1000-player/SpiderApp'
    lines=app_list.splitlines(keepends=True)
    matches=[i for i,line in enumerate(lines) if not line.lstrip().startswith(b'#')
             and line.split()==[b'0x00000001',b'*',original]]
    if len(matches)!=1:raise ValueError('Expected one stock player application registration')
    # SysMgr uses the command token as a lookup identity as well as an exec path.
    # Keep that registration exact; replace the entry executable with the wrapper
    # and relocate the single actual player payload instead of duplicating it.
    replacement=app_list
    out=ROOT/'work/player-system-layout'/str(time.time_ns());out.mkdir(parents=True)
    supervisor=None
    new_ownership={}
    page_review=None
    if args.host_review:
        from review_managed_remote_profile import receipt,artifact
        host_path,host=receipt(args.host_review)
        if not host.get('passed') or not host.get('analysis_only') or not host.get('remote_factory_automatic'):
            raise ValueError('Expected composed automatic analysis host')
        library=host_path.parent/'libx1000-player-analysis.so'
        payload=host_path.parent/'SpiderApp.player-prepare.analysis-only.elf'
        artifact(library,host['library_sha256'],host['library_bytes'])
        if hashlib.sha256(payload.read_bytes()).hexdigest()!=host['candidate_sha256']:raise ValueError('Player identity mismatch')
        _,supervisor_review=receipt(host['remote_factory_profile']['review'])
        supervisor=ROOT/supervisor_review['artifact']
        artifact(supervisor,supervisor_review['sha256'],supervisor_review['bytes'])
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            library,payload,host=build(managed_host=True,engine_provider=True,native_prepare=True,builtin_localization=True)
    libs=stock_libraries()
    wrapper=out/'x1000-player-start.arm'
    sources=['runtime/platform/player/bootstrap.c','runtime/store/start.c','runtime/store/start.S']
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                    '-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                    '-DXW_PLAYER_SYSTEM_PRELOAD','-DXW_PLAYER_PAYLOAD="/'+payload_path+'"',
                    '-DXW_PLAYER_ARGV0="SpiderApp"',
                    '-DXW_PLAYER_LIBRARY="/usr/local/lib/libx1000-player.so"',
                    '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector',
                    '-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none,-Ttext-segment=0x01000000',
                    *sources,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(wrapper)],cwd=ROOT,check=True)
    entries={payload_path:(payload.read_bytes(),0o755),
             'usr/local/lib/libx1000-player.so':(library.read_bytes(),0o644),
             wrapper_path:(wrapper.read_bytes(),0o755),
             'etc/AppList.conf':(replacement,0o644)}
    if supervisor:
        # Must match the host's compiled factory path, not an inferred relocation.
        header=ROOT/'runtime/apps/wireless-remote/supervisor_process.h'
        if host['source_hashes'].get(header.relative_to(ROOT).as_posix())!=hashlib.sha256(header.read_bytes()).hexdigest():raise ValueError('Supervisor path header not pinned by host')
        import re
        paths=re.findall(r'"(/usr/local/[^"\n]+)"',header.read_text())
        if len(paths)!=1:raise ValueError('Expected one compiled system supervisor path')
        entries[paths[0].lstrip('/')]=(supervisor.read_bytes(),0o755)
        composition=json.loads((ROOT/host['source_composition_report']).read_text())
        resource_review=composition.get('settings_resource_review')
        if not resource_review:raise ValueError('Host composition lacks paired menu resource provenance')
        resource_path,resources=receipt(resource_review)
        for name,row in resources['resource_overlay'].items():
            if not name.startswith('usr/local/share/gemini/res/'):raise ValueError('Unexpected menu resource destination')
            resource=resource_path.parent/'root-overlay'/name
            artifact(resource,row['sha256'],row['bytes'])
            if name not in resource_modes:raise ValueError('Resource lacks original metadata: '+name)
            entries[name]=(resource.read_bytes(),resource_modes[name])
        if host.get('native_remote_page_analysis'):
            page_path,page=receipt(host['native_remote_page_analysis'])
            if (page['sha256']!=host['candidate_sha256'] or
                set(page['resource_overlay'])!={REMOTE_RESOURCE} or
                REMOTE_RESOURCE in archive_names or REMOTE_RESOURCE in entries):
                raise ValueError('Remote page resource does not match the player layout')
            row=page['resource_overlay'][REMOTE_RESOURCE]
            if row['template']!=REMOTE_TEMPLATE:
                raise ValueError('Unexpected Remote page resource template')
            resource=page_path.parent/'root-overlay'/REMOTE_RESOURCE
            artifact(resource,row['sha256'],row['bytes'])
            if host['source_hashes'].get(resource.relative_to(ROOT).as_posix())!=row['sha256']:
                raise ValueError('Remote page resource is not pinned by the paired host')
            entries[REMOTE_RESOURCE]=(resource.read_bytes(),row['mode'])
            new_ownership[REMOTE_RESOURCE]=(row['uid'],row['gid'])
            page_review=page_path
    manifest={}
    for name,(data,mode) in entries.items():
        target=out/'root-overlay'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data);target.chmod(mode)
        manifest[name]=dict(bytes=len(data),mode=oct(mode),sha256=hashlib.sha256(data).hexdigest())
        if name in new_ownership:
            manifest[name]['uid'],manifest[name]['gid']=new_ownership[name]
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:
        localization_entries={m.name.removeprefix('./'):m for m in archive.getmembers()}
    growth=sum(len(data)-(localization_entries[name].size if name in localization_entries else 0) for name,(data,mode) in entries.items())
    stock_root=ROOT/'work/upg-jp/verified-3.bin'
    if hashlib.sha256(stock_root.read_bytes()).hexdigest()!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':raise ValueError('Original root identity mismatch')
    with tarfile.open(stock_root,mode='r:gz') as archive:
        stock_entries={m.name.removeprefix('./'):m for m in archive.getmembers()}
        accounting=[]
        for name,(data,mode) in entries.items():
            old=stock_entries.get(name)
            if old and not old.isfile():raise ValueError('Overlay would replace non-file: '+name)
            accounting.append(dict(path=name,original_bytes=old.size if old else 0,candidate_bytes=len(data),delta_bytes=len(data)-(old.size if old else 0)))
    report=dict(prepared=True,analysis_only=True,ready_to_flash=False,firmware_created=False,
                device_accessed=False,localization_input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                host_build=host,files=manifest,player_copies_in_final_layout=1,
                native_remote_page_review=page_review.relative_to(ROOT).as_posix() if page_review else None,
                regular_file_growth_over_localization_bytes=growth,
                overlay_accounting_against_original=accounting,
                overlay_regular_file_growth_over_original_bytes=sum(row['delta_bytes'] for row in accounting),
                whole_image_capacity_checked=False,
                original_player_payload_path='/'+payload_path,
                original_player_entry_path='/usr/local/bin/SpiderApp',
                bootstrap_path=wrapper_path,player_payload_path=payload_path,
                stock_registration_preserved=True,stock_lookup_name='SpiderApp',
                system_preload=True,inherited_test_grants_removed=True,
                controller_session_created=False,radio_enabled=False,
                source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest()
                               for s in [*sources,'tools/prepare_player_system_layout.py','tools/builtin_language.py',
                                         'tools/remote_choice_resource.py',
                                         *([page_review.relative_to(ROOT).as_posix()] if page_review else [])]},
                limits=['Root overlay only: no installer or UPG output.',
                        'Original sysmgr registration and full SpiderApp startup require hardware qualification.',
                        'Overlay accounting excludes other localization/menu resource changes and filesystem allocation.',
                        'Native Settings, RF power-off, persistent sessions and sleep require physical acceptance.'])
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=out.relative_to(ROOT).as_posix(),growth_bytes=growth,
                          player_copies=1,firmware_created=False),indent=2))

if __name__=='__main__':main()
