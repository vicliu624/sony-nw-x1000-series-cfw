"""Freeze a reviewed local diagnostic with Sony's untouched updater; never installs."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from app_registry import ROOT
from market_metadata import parse_version, compare_versions
from review_managed_remote_profile import digest, private, receipt, radio_dependencies
from review_managed_root_capacity import inventory, compose_root_inventory, read_localization_root
from test_firmware_regressions import source_inventory

sys.path.insert(0, str(ROOT / 'scripts'))
from upg import STOCK_SHA256, unpack

# Independently extracted from the pinned Japanese 1.11 Sony installer.
UPDATER_HASHES = {
    'FWUpdater.exe': '3cf7eb2e354d2e6d3f0cddd06ab67755696579a0d2cc85b68672ecc44ccb3c1c',
    'FWUpdaterCom.dll': '2b7550cd945a8d71d139063fce0ce006bfa6b59ee940f17e5151bdb6e35ebe2f',
    'FWUpdaterRes.dll': '0536de4cc4373f2f1391fbb52f11edf47af28fa52551959d569b6488c639b243',
    'NW-X10X0.ini': 'ff3d772ab446b3749272bf57b1c31b17765d4a807ff896de8b46f9bbb6dc11fa',
}


def checked_copy(source, target):
    if source.is_symlink() or not source.is_file():
        raise ValueError('Expected an ordinary reviewed input: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if target.stat().st_size != source.stat().st_size or digest(target) != digest(source):
        raise ValueError('Copy differs: ' + str(target))


def delivery_inputs(template, radio_directory, owner):
    """Resolve only the updater and RF files needed by the selected review."""
    stock = private(template / 'NW_WM_FW.UPG')
    if digest(stock) != STOCK_SHA256:
        raise ValueError('Original updater template differs')
    updater = {stock.name: stock}
    for name, expected in UPDATER_HASHES.items():
        source = private(template / name)
        if digest(source) != expected:
            raise ValueError('Sony updater identity differs: ' + name)
        updater[name] = source
    for source in sorted(template.glob('license_*.txt')):
        updater[source.name] = private(source)

    radio = {}
    prefix = '/contents/HOMEBREW/data/wireless-remote/candidate/'
    for row in radio_dependencies(owner)['immutable_inputs']:
        device_path = row['device_path']
        if device_path not in (prefix + 'sd8686.bin', prefix + 'helper_sd.bin'):
            raise ValueError('Unexpected external dependency path')
        source = private(radio_directory / Path(device_path).name)
        if source.stat().st_size != row['bytes'] or digest(source) != row['sha256']:
            raise ValueError('External RF input differs: ' + source.name)
        radio[device_path.removeprefix('/contents/')] = source
    return updater, radio


def reviewed_inputs(firmware_review, allocation_review, regressions):
    fp, firmware = receipt(firmware_review)
    mp, model = receipt(allocation_review)
    bp = private(regressions)
    bulk = json.loads(bp.read_text(encoding='utf-8'))
    if (not firmware.get('prepared') or not firmware.get('analysis_only') or
            firmware.get('ready_to_flash') or firmware.get('device_accessed')):
        raise ValueError('Expected an uninstalled diagnostic firmware review')
    if not model.get('passed') or model.get('physical_margin_verified'):
        raise ValueError('Expected an explicit PC allocation model')
    if not bulk.get('passed') or bulk.get('source_changed_during_run'):
        raise ValueError('Passing immutable regression snapshot required')
    snapshot = bulk.get('source_snapshot', (bp.parent / 'checked-source.zip').relative_to(ROOT).as_posix())
    if digest(private(snapshot)) != bulk['source_snapshot_sha256']:
        raise ValueError('Regression source snapshot changed')
    for check in bulk['checks']:
        if check['exit_code'] or digest(private(check['log'])) != check['log_sha256']:
            raise ValueError('Regression log changed or did not pass')
    current = source_inventory()
    changed = sorted(name for name in current.keys() | bulk['source_hashes'].keys()
                     if current.get(name) != bulk['source_hashes'].get(name))
    if any(name.startswith(('runtime/', 'sdk/', 'config/')) for name in changed):
        raise ValueError('Product sources changed after the regression run')
    layouts = [name for name, sha in firmware['inputs'].items()
               if sha == firmware['layout_review_sha256']]
    if len(layouts) != 1:
        raise ValueError('Ambiguous firmware layout')
    lp, layout = receipt(layouts[0])
    cp, capacity = receipt(model['capacity_review'])
    if (digest(cp) != model['capacity_review_sha256'] or
            digest(cp) != firmware['capacity_review_sha256'] or
            digest(lp) != capacity['layout_review_sha256']):
        raise ValueError('Firmware and dense allocation model differ')
    for name, expected in model['input_hashes'].items():
        if digest(private(name)) != expected:
            raise ValueError('Allocation input changed: ' + name)
    upg = private(firmware['artifact'])
    if digest(upg) != firmware['sha256']:
        raise ValueError('Firmware artifact changed')
    _, parts = unpack(upg.read_bytes(), require_stock=False)
    if parts[:3] != [private('work/upg-jp/verified-' + str(i) + '.bin').read_bytes()
                     for i in range(3)]:
        raise ValueError('Original installation components changed')
    actual = inventory(parts[3])
    _, base_root, localization_sha = read_localization_root(layout)
    if localization_sha != capacity['localization_sha256']:
        raise ValueError('Localization input differs from capacity review')
    if actual != compose_root_inventory(inventory(base_root), layout['files']):
        raise ValueError('Complete packaged root differs from reviewed layout')
    for name, row in layout['files'].items():
        if actual[name]['sha256'] != row['sha256'] or actual[name]['bytes'] != row['bytes']:
            raise ValueError('Packaged overlay differs: ' + name)
    extracted = fp.parent / 'rockbox-check'
    if any(private(extracted / ('part-' + str(i) + '.bin')).read_bytes() != part
           for i, part in enumerate(parts)):
        raise ValueError('Independent Rockbox extraction differs')
    binding = layout.get('remote_factory_profile', layout['host_build']['remote_factory_profile'])
    _, supervisor = receipt(binding['review'])
    if not supervisor.get('embedded_runtime'):
        raise ValueError('This material profile requires embedded Remote programs')
    _, owner = receipt(supervisor['shared_wifi_owner_review'])
    return dict(firmware=firmware, model=model, layout=layout, owner=owner, supervisor=supervisor, upg=upg,
                input_paths=(fp, mp, bp, lp, cp), subsequent_pc_changes=changed)


def matching_controller(owner, controller_review, *, play_mode_control=False, service_review=None):
    """Bind the controller image to the exact transport sources linked by Root."""
    if owner.get('negotiated_link_keys') is not True:
        if play_mode_control:
            raise ValueError('Mode-control delivery requires the negotiated-link controller profile')
        if controller_review is not None:
            raise ValueError('Controller delivery requires the negotiated-link firmware profile')
        return None
    if controller_review is None:
        raise ValueError('Negotiated-link firmware requires --controller-review')
    cp, controller = receipt(controller_review)
    if (controller.get('built') is not True or
            controller.get('target') != 'Core2 + Faces Gamepad3' or
            not isinstance(controller.get('version'), str)):
        raise ValueError('Expected a reviewed Core2 controller build')
    parse_version(controller['version'])
    player_protocol = None
    if play_mode_control:
        if (compare_versions(controller['version'], '0.1.0-alpha.31') < 0 or
                controller.get('play_mode_write_ui') is not True):
            raise ValueError('Mode-control firmware requires Core2 alpha.31 or newer with mode-write UI')
        if service_review is None:
            raise ValueError('Mode-control delivery requires the matching player service receipt')
        _, service = receipt(service_review)
        if service.get('command_negotiation_supported') is not True:
            raise ValueError('Mode-control service has no explicit command negotiation')
        player_names = ('runtime/platform/player/player.h',
                        'runtime/apps/wireless-remote/control.c', 'runtime/apps/wireless-remote/control.h',
                        'runtime/apps/wireless-remote/link.c', 'runtime/apps/wireless-remote/link.h',
                        'runtime/apps/wireless-remote/mode_wire.c', 'runtime/apps/wireless-remote/mode_wire.h')
        player_protocol = {name: controller['source_hashes'].get(name) for name in player_names}
        if any(sha is None or service['source_hashes'].get(name) != sha
               for name, sha in player_protocol.items()):
            raise ValueError('Player service and Core2 command protocol sources differ')
    required = ('runtime/platform/espnow/xnow_link.c', 'runtime/platform/espnow/xnow_link.h',
                'runtime/apps/wireless-remote/core2/src/main.cpp',
                'runtime/apps/wireless-remote/core2/src/link_transport.cpp',
                'runtime/apps/wireless-remote/core2/src/link_transport.h')
    if any(name not in controller['source_hashes'] for name in required):
        raise ValueError('Controller build does not include the negotiated-link adapter')
    linked = [(name, sha) for name, sha in owner['linked_input_hashes'].items()
              if name.endswith('/sdk/lib/libxnow.a')]
    if len(linked) != 1:
        raise ValueError('Expected one pinned native transport archive')
    archive = private(linked[0][0])
    if digest(archive) != linked[0][1]:
        raise ValueError('Linked native transport archive changed')
    np, native = receipt(archive.parent.parent / 'build.json')
    if native.get('archive_sha256') != linked[0][1]:
        raise ValueError('Native archive and its source receipt differ')
    transport = {name: controller['source_hashes'][name] for name in required[:2]}
    if any(native['source_hashes'].get(name) != sha for name, sha in transport.items()):
        raise ValueError('Root and Core2 transport sources differ')
    if owner['source_hashes'].get(required[1]) != transport[required[1]]:
        raise ValueError('Root and Core2 transport headers differ')
    image = controller.get('artifacts', {}).get('firmware.bin', {})
    binary = private(image.get('local', ''))
    if binary.stat().st_size != image.get('bytes') or digest(binary) != image.get('sha256'):
        raise ValueError('Controller firmware image changed')
    return dict(review=cp, native_review=np, binary=binary, version=controller['version'],
                bytes=image['bytes'], sha256=image['sha256'], transport_source_hashes=transport,
                play_mode_control=play_mode_control, player_protocol_source_hashes=player_protocol)


def instructions(version, reviewed, controller):
    model = reviewed['model']
    growth = model['used_growth_bytes'] / 1024
    margin = model['model_nonreserved_margin_bytes'] / 1048576
    controller_files = (f'- 04_CORE2: matching Core2 {controller["version"]} application and build receipt.\n'
                        '  It contains no bootloader, partition table, NVS or saved pairing data.\n') if controller else ''
    controller_requirement = (f'Use the matching Core2 {controller["version"]} application. If that exact\n'
                              '   image is already installed, keep it; a repeated flash is unnecessary.\n'
                              '   Controller updating must verify the actual\n'
                              '   application partition and preserve NVS; never erase the whole Flash.\n'
                              '   Keep the existing pairing.\n') if controller else (
                              'Use the controller matched to this legacy transport profile.\n'
                              '   Keep the existing pairing.\n')
    link_scope = ('The Root and Core2 transport sources match. Each connection negotiates a new\n'
                  'temporary encryption key; permanent pairing and old counter journals remain\n'
                  'unchanged. The shared-radio owner drains its endpoint, closes receive\n'
                  'membership and restores owed sleep state before releasing its native lease.\n') if controller else (
                  'This bundle retains its reviewed legacy controller protocol.\n')
    return f'''# NW-X1000 {version}: local firmware diagnostic

Japanese NW-X1050/NW-X1060 only; prepared for a Japanese NW-X1060 on Sony 1.11.
This is a manual diagnostic, not a stable release or hardware-qualified repair.
Sony's updater formats system storage normally. Interruption or installation
failure can prevent boot/USB recovery; the original package is not a recovery-mode
guarantee. No updater, drive operation or controller flash runs during preparation.

## Files

- 01_PC_UPDATE: unchanged Sony updater, DLLs, INI and licenses with this diagnostic UPG.
- 02_ORIGINAL_SONY: the original Sony 1.11 updater/package, preserved separately.
- 03_PLAYER_FILES: two immutable RF inputs and a fresh 2 KiB diagnostic record.
  It contains no pairing keys, configuration, PN journals, apps or saved games.
  Existing Homebrew launcher/apps stay in place. Remote programs and SDK library
  are embedded in the firmware; do not copy old owner.arm/service.arm files.
{controller_files}- SHA256SUMS.txt and materials.json: exact file identities and review provenance.

## Installation

1. If WALKMAN already has HOMEBREW/data/diagnostics/remote-pairing.bin, copy it
   to your computer before replacing it. Then merge 03_PLAYER_FILES/HOMEBREW
   into the WALKMAN root. Keep every other existing file, especially pairing
   configuration, session.keys and pn/. Do not format or repeat first-use setup.
2. With sufficient battery power, run 01_PC_UPDATE/FWUpdater.exe yourself.
   Use its normal controls. Do not change the INI/version checks, disconnect USB
   or press RESET while the updater/player reports an update in progress.
3. Wait for explicit completion and the automatic reboot. Safely eject and
   unplug USB. First check the original Home screen, touch/buttons and playback
   with Wireless Remote off. Report a failure before trying later stages.

## Staged checks after normal startup

1. Confirm Settings exposes Language and Wireless Remote. Check English and
   return navigation. Test a normal USB reconnect before enabling Remote.
2. Enter Homebrew, open Graphics and press HOME once. Check entry and return.
   To test Wi-Fi continuity separately, connect ordinary Wi-Fi first, enter
   Homebrew and open WiFi Terminal. Record its IP or exact error. A router is
   not a requirement for the separate ESP-NOW Remote test.
3. {controller_requirement}   Turn Wi-Fi on and then Wireless Remote on.
   Check state, play/pause, previous/next, volume and all five stock play modes.
   Do not re-pair just because reception fails.
4. Turn Wireless Remote off, then reconnect USB once. This tests the reported exit/handoff
   defect. If USB or the player stops responding, stop repeating the test and
   report the screen state. Never RESET during an active firmware update.
5. After successful USB access, copy HOMEBREW/data/diagnostics/remote-pairing.bin
   back to your computer for analysis. Its writes are fixed in a preallocated
   user-storage file; nothing is logged to a system partition.

## Scope

{link_scope}
No heartbeat or periodic status traffic is added. Diagnostics use a fixed
preallocated user-storage file. The complete ordinary 148 MiB ext2 allocation
model adds {growth:.0f} KiB over stock and leaves {margin:.2f} MiB after reserved blocks.

The candidate also contains the reviewed warm Homebrew handoff. Its C resource
drain/retained-lease/return chain passes, but original capture, screen/input release,
physical Wi-Fi association, sleep/wake and USB acceptance remain unqualified.
QEMU and capacity models are not physical acceptance. Report the first failing
stage; this package makes no automatic repair or recovery promise.
'''


def stage_materials(staging, reviewed, controller, updater, radio):
    for folder in ('01_PC_UPDATE', '02_ORIGINAL_SONY'):
        for name, source in updater.items():
            if folder == '01_PC_UPDATE' and name == 'NW_WM_FW.UPG':
                source = reviewed['upg']
            checked_copy(source, staging / folder / name)
    external = staging / '03_PLAYER_FILES'
    for name, source in radio.items():
        checked_copy(source, external / name)
    trace = external / 'HOMEBREW/data/diagnostics/remote-pairing.bin'
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_bytes(b'X1000-REMOTE-PAIRING-TRACE-1'.ljust(2048, b'\0'))
    if controller:
        checked_copy(controller['binary'], staging / '04_CORE2/firmware.bin')
        checked_copy(controller['review'], staging / '04_CORE2/build.json')
    (staging / 'READ_FIRST.md').write_text(instructions((ROOT / 'VERSION').read_text().strip(), reviewed, controller), encoding='utf-8')
    files = {p.relative_to(staging).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p))
             for p in sorted(staging.rglob('*')) if p.is_file()}
    manifest = dict(prepared=True, local_diagnostic=True, firmware_packaged=True,
                    installed=False, published=False,
                    hardware_qualified=False, device_accessed=False,
                    firmware_sha256=reviewed['firmware']['sha256'], files=files,
                    original_updater_unchanged=True, original_install_components_unchanged=True,
                    mutable_pairing_state_included=False, existing_apps_preserved=True,
                    input_reviews={p.relative_to(ROOT).as_posix(): digest(p) for p in reviewed['input_paths']},
                    subsequent_pc_source_changes=reviewed['subsequent_pc_changes'],
                    source_hashes={name:digest(ROOT / name) for name in (
                        'tools/prepare_diagnostic_materials.py', 'tools/review_managed_remote_profile.py',
                        'tools/review_managed_root_capacity.py', 'tools/test_firmware_regressions.py',
                        'scripts/upg.py', 'scripts/upg_crypto.py', 'tools/market_metadata.py')},
                    model_margin_bytes=reviewed['model']['model_nonreserved_margin_bytes'])
    if controller:
        manifest['controller'] = dict(version=controller['version'], file='04_CORE2/firmware.bin',
            bytes=controller['bytes'], sha256=controller['sha256'],
            transport_source_hashes=controller['transport_source_hashes'],
            nvs_included=False, automatic_flash=False)
        for path in (controller['review'], controller['native_review']):
            manifest['input_reviews'][path.relative_to(ROOT).as_posix()] = digest(path)
    (staging / 'materials.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (staging / 'SHA256SUMS.txt').write_text(''.join(row['sha256'] + '  ' + name + '\n'
                                                for name, row in files.items()), encoding='utf-8')
    for name in ('materials.json', 'SHA256SUMS.txt'):
        path = staging / name
        files[name] = dict(bytes=path.stat().st_size, sha256=digest(path))
    return files


def write_verified_archive(staging, archive, bundle_name, files):
    names = {bundle_name + '/' + name: row for name, row in files.items()}
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
        for name in sorted(files):
            bundle.write(staging / name, bundle_name + '/' + name)
    with zipfile.ZipFile(archive) as bundle:
        if sorted(bundle.namelist()) != sorted(names):
            raise ValueError('Archive file inventory differs')
        for name, row in names.items():
            with bundle.open(name) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if bundle.getinfo(name).file_size != row['bytes'] or actual != row['sha256']:
                raise ValueError('Archived file differs: ' + name)
    with archive.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def new_delivery_paths(output):
    archive = output.with_name(output.name + '.zip')
    checksum = archive.with_suffix('.zip.sha256')
    if any(path.exists() or path.is_symlink() for path in (output, archive, checksum)):
        raise FileExistsError('Diagnostic output already exists: ' + str(output))
    return archive, checksum


def assemble_materials(output, reviewed, controller, updater, radio):
    archive, checksum = new_delivery_paths(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.diagnostic-materials-', dir=output.parent) as folder:
        temporary = Path(folder)
        staging = temporary / output.name
        staged_archive = temporary / archive.name
        staged_checksum = temporary / checksum.name
        files = stage_materials(staging, reviewed, controller, updater, radio)
        archive_sha256 = write_verified_archive(staging, staged_archive, output.name, files)
        staged_checksum.write_text(archive_sha256 + '  ' + archive.name + '\n', encoding='utf-8')

        # Claim both file names exclusively before publishing. Another packer
        # targeting the same name cannot replace this run's files.
        with ExitStack() as rollback:
            for target, prepared in ((archive, staged_archive), (checksum, staged_checksum)):
                target.touch(exist_ok=False)
                rollback.callback(target.unlink)
                prepared.replace(target)
            if output.exists() or output.is_symlink():
                raise FileExistsError(output)
            staging.rename(output)
            rollback.pop_all()
    return archive, archive_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-review', required=True)
    parser.add_argument('--allocation-review', required=True)
    parser.add_argument('--regression-review', required=True)
    parser.add_argument('--controller-review', help='Required matching Core2 build for negotiated-link firmware')
    parser.add_argument('--updater-template', type=Path, required=True, help='Stock UPG, updater files and licenses under work/')
    parser.add_argument('--radio-inputs', type=Path, required=True, help='Directory under work/ containing reviewed external radio files')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    dist = (ROOT / 'dist').resolve()
    if args.output.is_symlink() or not output.is_relative_to(dist) or output == dist:
        raise ValueError('Use a new local directory under dist/')
    new_delivery_paths(output)
    reviewed = reviewed_inputs(args.firmware_review, args.allocation_review, args.regression_review)
    supervisor = reviewed['supervisor']
    service_path = private(supervisor['local_inputs']['service']['local']).parent / 'build.json'
    controller = matching_controller(reviewed['owner'], args.controller_review,
                                     play_mode_control=bool(supervisor.get('play_mode_control')),
                                     service_review=service_path)
    updater, radio = delivery_inputs(ROOT / args.updater_template, ROOT / args.radio_inputs, reviewed['owner'])
    archive, archive_sha256 = assemble_materials(output, reviewed, controller, updater, radio)
    print(json.dumps(dict(prepared=True, directory=output.relative_to(ROOT).as_posix(),
                          archive=archive.relative_to(ROOT).as_posix(), archive_sha256=archive_sha256,
                          firmware_sha256=reviewed['firmware']['sha256'], device_accessed=False)))


if __name__ == '__main__':
    main()
