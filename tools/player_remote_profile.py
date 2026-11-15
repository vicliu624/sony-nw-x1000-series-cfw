"""Validate the selected Remote deployment and derive the player host contract."""
import json

from component_receipts import ROOT, artifact, component_build, digest, private, receipt, validate_linked_inputs


def input_artifact(supervisor, name, leaf):
    item = supervisor['inputs'][name]
    local = supervisor['local_inputs'][name]
    if local['sha256'] != item['sha256'] or local['bytes'] != item['bytes']:
        raise ValueError('Input receipts differ: ' + name)
    path = private(local['local'])
    if path.name != leaf:
        raise ValueError('Expected reviewed ' + name + ' artifact name')
    result = artifact(path, item['sha256'], item['bytes'])
    if name in ('owner', 'service'):
        _, _, built_identity = component_build(path.parent / 'build.json', leaf)
        if built_identity != result:
            raise ValueError('Component build receipt differs: ' + name)
    return path, result


def player_remote_inputs(supervisor_review, radio_review=None):
    """Validate the selected deployment inputs and derive the host's compile flags."""
    profile_path, profile = receipt(supervisor_review)
    if not profile.get('built') or not profile.get('reusable_sessions'):
        raise ValueError('Reusable supervisor review required')
    validate_linked_inputs(profile)
    if not 0 < profile['bytes'] <= 1048576:
        raise ValueError('Supervisor size outside the supported range')
    executable = artifact(profile['artifact'], profile['sha256'], profile['bytes'])
    owner_path, owner_identity = input_artifact(profile, 'owner', 'remote-rf-owner.arm')
    input_artifact(profile, 'service', 'wireless-remote-service.arm')

    embedded = bool(profile.get('embedded_runtime'))
    root_cold = bool(profile.get('root_cold_supported'))
    pairing = bool(profile.get('device_pairing'))
    owner_view = bool(profile.get('owner_mode_view_forwarded'))
    if root_cold and not (radio_review and embedded):
        raise ValueError('Cold remote requires the embedded shared Wi-Fi profile')
    if pairing and not radio_review:
        raise ValueError('Device pairing requires the shared Wi-Fi profile')
    image_path = None
    if radio_review is not None:
        if not owner_view or not profile.get('shared_wifi_owner_review'):
            raise ValueError('Expected supervisor pinned to a reviewed shared Wi-Fi owner')
        reviewed_owner = private(profile['shared_wifi_owner_review'])
        if reviewed_owner != owner_path.parent / 'build.json':
            _, _, shared_identity = component_build(reviewed_owner, owner_path.name)
            if any(shared_identity[key] != owner_identity[key] for key in ('sha256', 'bytes')):
                raise ValueError('Shared Wi-Fi owner does not match the supervisor input')
        _, owner = receipt(reviewed_owner)
        if (not owner.get('shared_wifi_supported') or
                owner['candidate_sha256'] != profile.get('shared_wifi_radio_sha256')):
            raise ValueError('Shared Wi-Fi owner radio differs from the supervisor review')
        image_path = private(radio_review)
        image = json.loads(image_path.read_text(encoding='utf-8'))
        if not image.get('rx_initially_disabled') or set(image['overlay']) != {'lib/modules/sd8686.bin'}:
            raise ValueError('Expected shared Wi-Fi image overlay')
        row = image['overlay']['lib/modules/sd8686.bin']
        candidate = private(row['artifact'])
        if row['sha256'] != profile.get('shared_wifi_radio_sha256') or not candidate.is_relative_to(image_path.parent):
            raise ValueError('Shared Wi-Fi image does not match the reviewed owner')
        artifact(candidate, row['sha256'], row['bytes'])
        if 'radio_build_sha256' in image:
            build_path, radio = receipt(image['radio_build'])
            if (digest(build_path) != image['radio_build_sha256'] or
                    radio['candidate_sha256'] != row['sha256']):
                raise ValueError('Shared Wi-Fi build receipt differs from the overlay')

    contract = dict(supervisor_bytes=profile['bytes'], embedded_runtime=embedded,
                    root_cold_supported=root_cold, device_pairing=pairing,
                    owner_mode_view_forwarded=owner_view, shared_wifi=image_path is not None,
                    play_mode_control=bool(profile.get('play_mode_control')))
    binding = dict(review=profile_path.relative_to(ROOT).as_posix(),
                   supervisor_artifact=executable['local'], sha256=executable['sha256'], bytes=executable['bytes'],
                   inputs=profile['inputs'], owner_mode_view_forwarded=owner_view,
                   play_mode_control=contract['play_mode_control'], software_admission_only=True,
                   hardware_qualified=False)
    return contract, binding, profile, image_path


def player_remote_header(contract):
    lines = ['#ifndef XW_REMOTE_FACTORY_PROFILE_H', '#define XW_REMOTE_FACTORY_PROFILE_H',
             '#define XW_PLAYER_REMOTE_FACTORY',
             f"#define WR_REMOTE_SUPERVISOR_BYTES {contract['supervisor_bytes']}u"]
    if contract['owner_mode_view_forwarded']:
        lines.append('#define WR_REMOTE_OWNER_VIEW')
    if contract['root_cold_supported']:
        lines.extend(('#define WR_REMOTE_ROOT_COLD', '#define WR_PAIRING_TRACE',
                      '#define XW_TRACE_STORE_PATH "/contents/HOMEBREW/data/diagnostics/remote-pairing.bin"'))
    if contract['device_pairing']:
        lines.append('#define WR_PAIRING_PROCESS')
    if contract['shared_wifi']:
        lines.append('#define XW_PLAYER_SHARED_WIFI_ANALYSIS')
    return '\n'.join([*lines, '#endif', ''])


def select_player_remote_inputs(host, supervisor_review=None, radio_review=None):
    original = host['remote_factory_profile']
    original_radio = host.get('shared_wifi_review')
    replacing = supervisor_review is not None or radio_review is not None
    expected = host.get('remote_factory_contract')
    if replacing and expected is None:
        raise ValueError('Supervisor replacement requires a host build with a recorded compile contract')
    contract, binding, profile, image = player_remote_inputs(
        supervisor_review if supervisor_review is not None else original['review'],
        radio_review if radio_review is not None else original_radio)
    if expected is not None and contract != expected:
        fields = ', '.join(name for name, value in contract.items() if expected.get(name) != value)
        raise ValueError('Remote inputs require rebuilding the player host: ' + fields)
    if not replacing and any(binding[key] != original[key] for key in ('sha256', 'bytes', 'inputs')):
        raise ValueError('Host/supervisor review differs')
    return binding, profile, image
