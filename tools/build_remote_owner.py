"""Build a Radio Owner from explicitly reviewed local inputs. PC-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import threading
import time

from app_registry import ROOT
from generate_espnow_full_profile import profile_header, reviewed_radio, verify_image
from owner_native_profile import file_initializer, render as render_native_profile, stock_header
from player_arm_guest import stock_libraries
from review_managed_remote_profile import digest, native_sdk_build, private, receipt
from sdk_build import fresh_work


def build(*, sdk_review=None, rx_diagnostic_radio=None, external_radio_inputs=None,
          legacy_radio=False, output=None,
          window_seconds=None, power_off_exit=False, mode_view_required=False,
          managed_session=False, root_cold=False, data_leaf='espnow-test', link_keys=False):
    if root_cold and not managed_session:
        raise ValueError('--root-cold requires --managed-session')
    if rx_diagnostic_radio is not None and not root_cold:
        raise ValueError('--rx-diagnostic-radio requires --root-cold')
    if legacy_radio == (rx_diagnostic_radio is not None):
        raise ValueError('Select --rx-diagnostic-radio or --legacy-radio')
    if legacy_radio and root_cold:
        raise ValueError('Root owner requires an explicit RX diagnostic radio review')
    if not legacy_radio and external_radio_inputs is None:
        raise ValueError('Root owner requires --external-radio-inputs')
    if link_keys and (not managed_session or not root_cold or data_leaf != 'wireless-remote'):
        raise ValueError('--link-keys requires the managed root profile and wireless-remote binding')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', data_leaf):
        raise ValueError('Data leaf must be a single lowercase application directory')
    if mode_view_required and not power_off_exit:
        raise ValueError('Mode-view owner requires power-off-exit profile')
    if managed_session and (not mode_view_required or window_seconds is not None):
        raise ValueError('Managed session requires mode-view-required and no finite window argument')
    if window_seconds not in (None, 60, 180):
        raise ValueError('Unsupported finite owner window')

    version = (ROOT / 'runtime/platform/espnow/VERSION').read_text().strip()
    if sdk_review is None:
        raise ValueError('Radio Owner requires --sdk-review')
    sdk_receipt, archive, sdk = native_sdk_build(sdk_review)
    if sdk.get('version') != version:
        raise ValueError('Native SDK version differs from the current source')
    crypto = ROOT / 'work/external-tls-probe/arm-build/libbearssl.a'
    if digest(crypto) != sdk['bearssl_archive_sha256']:
        raise ValueError('Native SDK BearSSL input changed')

    if legacy_radio:
        manifest_path = private('work/espnow-full-radio-review-3/manifest.json')
        review = manifest_path.parent
        payload = private(review / 'radio.elf')
        private(review / 'stock/sd8686.bin')
        private(review / 'candidate/sd8686.bin')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if (manifest['candidate_sha256'] != 'd4b92b65fa502e2c8c94d241e4a293e28db7e98a3afdba0958d8b4f8aa1a5ed8' or
                manifest['payload_elf_sha256'] != '6918e3996088ebd99924e8c7039ad6ed26555aa3b0c411f2b9f765334c2218df'):
            raise ValueError('Legacy radio review differs')
        verify_image(review, manifest)
    else:
        payload, manifest = reviewed_radio(rx_diagnostic_radio)
        review = payload.parent
    manifest_path = review / 'manifest.json'
    radio = review / 'candidate/sd8686.bin'
    radio_inputs = [path.relative_to(ROOT).as_posix() for path in
                    (manifest_path, radio, payload, review / 'stock/sd8686.bin')]
    if not legacy_radio:
        radio_inputs.append((review / 'candidate/helper_sd.bin').relative_to(ROOT).as_posix())
    radio_inputs += ['tools/generate_espnow_full_profile.py', 'tools/build_espnow_full_radio.py']
    profile = profile_header(manifest)
    if not legacy_radio and (not manifest.get('rx_diagnostics') or 'XNOW_RADIO_RX_SEEN' not in profile):
        raise ValueError('Expected an exact-image RX diagnostic profile')
    radio_source_hashes = {} if legacy_radio else manifest['source_hashes']

    stock_root = private('work/upg-jp/verified-3.bin')
    stock_manifest = stock_header(stock_root)
    data_directory = '/contents/HOMEBREW/data/' + data_leaf
    # The retained user-volume RF pair belongs to the legacy loader. Root
    # profiles use the selected system image, but keep the same input table
    # for the separately checked external files in existing diagnostic kits.
    external_radio = ROOT / (external_radio_inputs if external_radio_inputs is not None else review / 'candidate')
    exchange = ['static const struct stock_input exchange_inputs[]={']
    external_hashes = {}
    for name, expected in (
        ('sd8686.bin', 'd4b92b65fa502e2c8c94d241e4a293e28db7e98a3afdba0958d8b4f8aa1a5ed8'),
        ('helper_sd.bin', 'b0157d1f4518e806c0bc5128ab302a7f97d78ee34b84cb41cb4f2bbbb2a00e6d'),
    ):
        path = private(external_radio / name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Legacy radio input differs: ' + name)
        exchange.append(file_initializer(data_directory + '/candidate/' + name, data))
        external_hashes[path.relative_to(ROOT).as_posix()] = expected
    exchange_header = '\n'.join([*exchange, '};']) + '\n'

    out = fresh_work(output or ROOT / 'work/remote-owner-build' / str(time.time_ns()))
    (out/'full_profile.h').write_text(profile, encoding='utf-8')
    (out/'exchange_inputs.h').write_text(exchange_header, encoding='utf-8')
    (out/'native_inputs.h').write_text(render_native_profile(stock_manifest, exchange_header), encoding='utf-8')
    if managed_session:
        sha = manifest['candidate_sha256']
        (out/'shared_wifi_input.h').write_text(
            'static const struct xnow_native_file shared_wifi_radio_input={"/lib/modules/sd8686.bin",'+
            str(radio.stat().st_size)+',{'+','.join('0x'+sha[i:i+2] for i in range(0,64,2))+'}};\n')
    libs=stock_libraries(include_rt=mode_view_required);cnmgr=ROOT/'work/stock-resolver-probe/libcnmgr.so.1'
    assert digest(cnmgr)=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
    sources=['runtime/apps/wireless-remote/rf_owner.c','runtime/platform/espnow/native_environment.c']
    if managed_session:sources+=['runtime/apps/wireless-remote/run_profile.c','runtime/apps/wireless-remote/pairing_store.c']
    sources+=['runtime/platform/espnow/'+n+'.c' for n in ('xnow_owner_gate','xnow_owner_runtime','xnow_owner_stream','xnow_owner_commands','xnow_owner_commands_control','xnow_handoff_owner','xnow_loader_job')]
    sources+=['runtime/store/start.c','runtime/store/start.S']
    if power_off_exit:sources+=['runtime/apps/wireless-remote/radio_stop.c','runtime/platform/wireless/radio_release.c','runtime/platform/espnow/xnow_power_off.c','runtime/platform/wireless/radio_modules.c']
    if mode_view_required:sources+=['runtime/apps/wireless-remote/owner_admission.c','runtime/platform/wireless/mode_client.c','runtime/platform/wireless/mode_channel.c','runtime/platform/wireless/mode_policy.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/deadline.c']
    flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-misleading-indentation','-D_DEFAULT_SOURCE=','-DHB_STORE_SONY_LIBC',
           '-DXNOW_REMOTE_WINDOW_MS='+str((window_seconds or 60)*1000)+'u',
           '-DXNOW_CANDIDATE_DIRECTORY="'+('/lib/modules' if root_cold else data_directory+'/candidate')+'"','-DXNOW_USER_DATA_LEAF="'+data_leaf+'"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
           '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie',
           '-Wl,--hash-style=sysv,--build-id=none,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
           '-I'+str(out),'-I'+str(ROOT/'runtime/platform/espnow'),
           '-I'+str(ROOT/'work/external-tls-probe/bearssl-0.6/inc')]
    if power_off_exit:flags+=['-DXNOW_REMOTE_POWER_OFF']
    if mode_view_required:flags+=['-DXNOW_REMOTE_MODE_VIEW','-DHB_STORE_LIBC_CLOCK']
    if managed_session:flags+=['-DXNOW_REMOTE_MANAGED']
    if root_cold:flags+=['-DXNOW_REMOTE_ROOT_COLD']
    if link_keys:flags+=['-DXNOW_REMOTE_LINK_KEYS']
    artifact=out/'remote-rf-owner.arm'
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(archive),str(crypto),str(cnmgr),
                    '-Wl,--no-as-needed',str(libs['libpthread.so.0']),*([str(libs['librt.so.1'])] if mode_view_required else []),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
    base=['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in [*libs.values(),cnmgr])),str(artifact)]
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    for args,expected in [(['--help'],0),([],64),(['--owner','3','3','4','00'*16,'020102030405','--charger-confirmed','--exclusive-radio-confirmed'],64)]:
     run=subprocess.run(base+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10);assert run.returncode==expected,run.stdout+run.stderr
    startup_refusal=False;mode_admission_cases=[]
    if not mode_view_required and '/dev/root / ext2 ro' not in Path('/proc/mounts').read_text():
     pairs=[os.pipe() for _ in range(3)];cookie=bytes(range(1,17))
     try:
      child_fds=[pairs[0][0],pairs[1][1],pairs[2][1]]
      run=subprocess.run(base+['--owner',*map(str,child_fds),cookie.hex(),'020102030405','--charger-confirmed','--exclusive-radio-confirmed'],
                         cwd=ROOT,env=env,pass_fds=child_fds,capture_output=True,text=True,timeout=10)
      assert run.returncode==69 and 'REMOTE_RF_OWNER_STARTING' not in run.stdout,run.stdout+run.stderr
      os.close(pairs[2][1]);pairs[2]=(pairs[2][0],-1)
      assert os.read(pairs[2][0],33)==b'XRFDONE1'+cookie+bytes([1,0,0,0,1,0,0,0])
      assert os.read(pairs[2][0],1)==b''
      startup_refusal=True
     finally:
      for pair in pairs:
       for fd in pair:
        if fd>=0:os.close(fd)
    if mode_view_required:
     assert '/dev/root / ext2 ro' not in Path('/proc/mounts').read_text(),'PC-only refusal checks require a non-Sony root'
     for kind in ('matching','wrong-lease','revoked'):
      pairs=[os.pipe() for _ in range(3)];server,client=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM);server.settimeout(3)
      cookie=bytes(range(1,17));errors=[]
      def authority():
       try:
        request=server.recv(33);assert len(request)==32 and request[:4]==b'WMC1' and struct.unpack_from('<I',request,4)[0]==1 and struct.unpack_from('<I',request,16)[0]==0
        serial=struct.unpack_from('<Q',request,8)[0];reply=bytearray(80);reply[:4]=b'WMS1'
        struct.pack_into('<IQ',reply,4,1,serial)
        for offset,value in ((16,0),(20,3 if kind=='revoked' else 2),(24,2),(28,1 if kind=='revoked' else 2),(32,1),(36,0),(64,2),(68,1)):struct.pack_into('<I',reply,offset,value)
        struct.pack_into('<QQQ',reply,40,77,13 if kind=='wrong-lease' else 12,99)
        server.send(reply)
       except BaseException as error:errors.append(repr(error))
      thread=threading.Thread(target=authority);thread.start()
      try:
       fds=[pairs[0][0],pairs[1][1],pairs[2][1],client.fileno()]
       args=['--owner',*map(str,fds[:3]),cookie.hex(),'020102030405','--charger-confirmed','--exclusive-radio-confirmed','--mode-view',str(fds[3]),'77','12','99']
       run=subprocess.run(base+args,cwd=ROOT,env=env,pass_fds=fds,capture_output=True,text=True,timeout=10)
       thread.join(4);assert not thread.is_alive() and not errors,errors
       assert run.returncode==69 and 'REMOTE_RF_OWNER_STARTING' not in run.stdout,run.stdout+run.stderr
       admitted='REMOTE_RF_MODE_VIEW_AUTHORIZED' in run.stdout;assert admitted==(kind=='matching')
       os.close(pairs[2][1]);pairs[2]=(pairs[2][0],-1)
       assert os.read(pairs[2][0],33)==b'XRFDONE1'+cookie+bytes([1,0,0,0,1,0,0,0]) and os.read(pairs[2][0],1)==b''
       mode_admission_cases.append(dict(case=kind,admitted=admitted,refused_before_radio=True,returncode=run.returncode))
       if admitted:startup_refusal=True
      finally:
       server.close();client.close();thread.join(4)
       for pair in pairs:
        for fd in pair:
         if fd>=0:os.close(fd)
    baseline_sha256=None
    diagnostic_sources=[]
    if legacy_radio:
        baseline=out/'espnow-test-baseline.arm'
        diagnostic_sources=['runtime/apps/espnow-test/main.c','runtime/apps/espnow-test/runner.c','runtime/apps/espnow-test/detached.c']
        subprocess.run(['arm-linux-gnueabi-gcc',*flags,*diagnostic_sources,*sources[1:],str(archive),str(crypto),str(cnmgr),
                        '-Wl,--no-as-needed',str(libs['libpthread.so.0']),*([str(libs['librt.so.1'])] if mode_view_required else []),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(baseline)],cwd=ROOT,check=True)
        for args,expected in [(['--help'],0),([],64)]:
            run=subprocess.run(base[:-1]+[str(baseline)]+args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            assert run.returncode==expected,run.stdout+run.stderr
        baseline_sha256=digest(baseline)
    inputs=sources+diagnostic_sources+radio_inputs+['runtime/platform/espnow/native_entry.h',
     'runtime/platform/espnow/native_environment.h','tools/owner_native_profile.py','tools/build_remote_owner.py',
     (out/'native_inputs.h').relative_to(ROOT).as_posix()]
    if legacy_radio:inputs.append('runtime/apps/espnow-test/runner.h')
    if power_off_exit:inputs+=['runtime/platform/wireless/radio_release.h','runtime/platform/wireless/radio_modules.h']
    if mode_view_required:inputs+=['runtime/apps/wireless-remote/owner_admission.h','runtime/platform/wireless/mode_client.h','runtime/platform/wireless/mode_channel.h','runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h','runtime/store/deadline.h']
    inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/espnow').glob('*.h')]
    inputs += [p.relative_to(ROOT).as_posix() for p in (stock_root, sdk_receipt, out/'full_profile.h', out/'exchange_inputs.h')]
    if managed_session:inputs.append((out/'shared_wifi_input.h').relative_to(ROOT).as_posix())
    inputs.append('runtime/apps/wireless-remote/pairing_proof.h')
    inputs.append('runtime/apps/wireless-remote/run_profile.h')
    inputs.append('runtime/apps/wireless-remote/startup_result.h')
    inputs.append('runtime/apps/wireless-remote/pairing_store.h')
    report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,sha256=digest(artifact),
                original_libc_arm_entry_checks=True,lab_only=True,window_seconds=None if managed_session else window_seconds,radio_started=False,device_accessed=False,
                finite_owner=not managed_session,lifetime_mode='supervised-session' if managed_session else 'finite-qualification',ready_for_native_settings=False,
                owner_mode_view_supported=mode_view_required,owner_mode_view_required=mode_view_required,mode_admission_cases=mode_admission_cases,
                shared_wifi_supported=managed_session,
                root_cold_supported=root_cold,
                negotiated_link_keys=link_keys,
                continuous_mode_refresh_compiled=mode_view_required,mode_refresh_ms=200 if mode_view_required else 0,mode_stale_ms=1000 if mode_view_required else 0,
                power_off_exit_profile=power_off_exit,
                borrowed_stock_wifi_allowed=managed_session or not power_off_exit,
                legacy_default_entry_checks=legacy_radio,baseline_sha256=baseline_sha256,
                non_sony_root_startup_refusal_receipt=startup_refusal,
                data_directory=data_directory,exchange_header=str((out/'exchange_inputs.h').relative_to(ROOT)),exchange_header_sha256=digest(out/'exchange_inputs.h'),
                candidate_sha256=manifest['candidate_sha256'],
                source_hashes={**{p:digest(ROOT/p) for p in inputs},**radio_source_hashes,**external_hashes},
                linked_input_hashes={str(p.relative_to(ROOT)):digest(p) for p in (archive,crypto,cnmgr,*libs.values())},
                limits=['No hardware run or physical acceptance.','Legacy test storage/context remains unqualified for production.','Cooperative custom exclusion is not global Sony Wi-Fi/APF/USB/sleep arbitration.',
                        'Power-off-exit controller compiled; physical radio-off remains unqualified.' if power_off_exit else 'Default controller restores stock driver without proving radio-off.',
                        'Supervised lifetime compiled; persistent native Settings operation remains unqualified.' if managed_session else 'Finite test owner must not be presented as a persistent native Settings remote.'])
    (out/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    receipt(out/'build.json')
    return artifact, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window-seconds', type=int, choices=(60, 180))
    parser.add_argument('--power-off-exit', action='store_true')
    parser.add_argument('--mode-view-required', action='store_true')
    parser.add_argument('--managed-session', action='store_true')
    parser.add_argument('--root-cold', action='store_true')
    parser.add_argument('--data-leaf', default='espnow-test')
    parser.add_argument('--sdk-review', type=Path, required=True, help='Native ESP-NOW SDK build.json under work/')
    parser.add_argument('--external-radio-inputs', type=Path, help='Pinned legacy RF files for the diagnostic kit under work/')
    parser.add_argument('--output', type=Path)
    radio = parser.add_mutually_exclusive_group(required=True)
    radio.add_argument('--rx-diagnostic-radio', type=Path, help='Reviewed exact-image build directory under work/')
    radio.add_argument('--legacy-radio', action='store_true', help='Use the pinned user-volume lab radio profile')
    parser.add_argument('--link-keys', action='store_true')
    try:
        _, report = build(**vars(parser.parse_args()))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
