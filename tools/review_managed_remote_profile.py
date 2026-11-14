"""Cross-check private managed components; emit review metadata, never install files."""
import argparse,hashlib,json,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=(ROOT/'work').resolve()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def private(path):
 path=Path(path)
 if not path.is_absolute():path=ROOT/path
 if path.is_symlink():raise ValueError('Receipt/artifact must not be a symlink')
 path=path.resolve()
 if not path.is_relative_to(WORK) or not path.is_file():raise ValueError('Expected existing private work input')
 return path
def receipt(path):
 path=private(path);data=json.loads(path.read_text(encoding='utf-8'))
 for name,expected in data['source_hashes'].items():
  source=(ROOT/name).resolve()
  if not source.is_relative_to(ROOT) or not source.is_file() or digest(source)!=expected:raise ValueError('Stale source/input: '+name)
 return path,data
def artifact(path,expected,size):
 path=private(path)
 if path.stat().st_size!=size or digest(path)!=expected:raise ValueError('Artifact identity mismatch: '+path.name)
 return dict(local=path.relative_to(ROOT).as_posix(),bytes=size,sha256=expected)


def native_sdk_build(path):
    path, build = receipt(path)
    archive = path.parent / 'lib/libxnow.a'
    if path.name != 'build.json' or build.get('built') is not True:
        raise ValueError('Expected a native ESP-NOW SDK build receipt')
    identity = artifact(archive, build['archive_sha256'], build['archive_bytes'])
    for name, expected in build.get('abi_library_hashes', {}).items():
        if digest(private((ROOT / name).resolve())) != expected:
            raise ValueError('Native SDK ABI library changed: ' + name)
    return path, ROOT / identity['local'], build


def component_build(path,leaf):
 path,built=receipt(path)
 if (path.name!='build.json' or built.get('built') is not True or
     not isinstance(built.get('artifact'),str)):
  raise ValueError('Component build receipt differs: '+leaf)
 executable=private(built['artifact'])
 if executable!=path.parent/leaf:
  raise ValueError('Component build receipt differs: '+leaf)
 for key in ('linked_input_hashes','linked_library_hashes'):
  for name,expected in built.get(key,{}).items():
   linked=(ROOT/name.replace('\\','/')).resolve()
   if digest(private(linked))!=expected:
    raise ValueError('Component linked input differs: '+name)
 return path,built,artifact(executable,built['sha256'],built['bytes'])
def input_artifact(supervisor,name,leaf):
 item=supervisor['inputs'][name]
 local=supervisor['local_inputs'][name]
 if local['sha256']!=item['sha256'] or local['bytes']!=item['bytes']:raise ValueError('Input receipts differ: '+name)
 path=private(local['local'])
 if path.name!=leaf:raise ValueError('Expected reviewed '+name+' artifact name')
 result=artifact(path,item['sha256'],item['bytes'])
 if name in ('owner','service'):
  # Parent identity does not prove that a cached child still represents current
  # source. Configuration is mutable data and deliberately has no code receipt.
  _,_,built_identity=component_build(path.parent/'build.json',leaf)
  if built_identity!=result:
   raise ValueError('Component build receipt differs: '+name)
 return path,result


def player_remote_inputs(supervisor_review, radio_review=None):
    """Validate the selected deployment inputs and derive the host's compile flags."""
    profile_path, profile = receipt(supervisor_review)
    if not profile.get('built') or not profile.get('reusable_sessions'):
        raise ValueError('Reusable supervisor review required')
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


def radio_dependencies(owner):
 """Inventory compiled immutable inputs without reading pairing keys or journals."""
 directory=owner['data_directory']
 if not re.fullmatch(r'/contents/HOMEBREW/data/[a-z][a-z0-9-]{0,47}',directory):raise ValueError('Invalid owner data directory')
 header=private(owner['exchange_header'])
 if digest(header)!=owner['exchange_header_sha256']:raise ValueError('Owner dependency header changed')
 rows=[]
 for path,size,raw in re.findall(r'\{"([^"\n]+)",(\d+),\{([0-9,]+)\}\}',header.read_text()):
  values=bytes(int(value) for value in raw.split(','))
  if len(values)!=32 or path.rsplit('/',1)[0]!=directory+'/candidate':
   raise ValueError('Unexpected compiled radio dependency')
  rows.append(dict(device_path=path,bytes=int(size),sha256=values.hex(),storage='user-volume',device_presence_verified=False))
 if {row['device_path'].rsplit('/',1)[-1] for row in rows}!={'sd8686.bin','helper_sd.bin'}:
  raise ValueError('Incomplete compiled radio dependency inventory')
 return dict(immutable_inputs=rows,immutable_payload_bytes=sum(row['bytes'] for row in rows),
  pairing=dict(device_path=directory+'/session.keys',bytes=32,contents_read=False,paired_controller_verified=False),
  packet_numbers=dict(device_path=directory+'/pn',preserve_existing=True,seed_or_reset_permitted=False),
  compiled_header=dict(local=header.relative_to(ROOT).as_posix(),sha256=digest(header)),
  installation_complete=False)
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--host-review',type=Path,required=True)
 args=parser.parse_args()
 host_path,host=receipt(args.host_review)
 if host_path.name!='build.json' or not host.get('passed') or not host.get('analysis_only') or not host.get('native_sleep_analysis') or not host.get('remote_factory_automatic'):raise ValueError('Expected composed automatic sleep-analysis host receipt')
 factory=host['remote_factory_profile']
 if not factory.get('owner_mode_view_forwarded'):raise ValueError('Owner mode-view forwarding required')
 supervisor_path,supervisor=receipt(factory['review'])
 if not supervisor.get('built') or not supervisor.get('reusable_sessions') or not supervisor.get('owner_mode_view_forwarded'):raise ValueError('Expected reusable mode-view supervisor')
 components={}
 components['supervisor']=artifact(ROOT/supervisor['artifact'],factory['sha256'],factory['bytes'])
 if components['supervisor']['sha256']!=supervisor['sha256']:raise ValueError('Host/supervisor review differs')
 owner_path,components['owner']=input_artifact(supervisor,'owner','remote-rf-owner.arm')
 owner_receipt,owner=receipt(owner_path.parent/'build.json')
 for flag in ('built','owner_mode_view_required','power_off_exit_profile','continuous_mode_refresh_compiled'):
  if not owner.get(flag):raise ValueError('Real owner contract missing: '+flag)
 if owner.get('finite_owner') is not False or owner.get('lifetime_mode')!='supervised-session':raise ValueError('Synthetic/finite owner is not a managed owner')
 if digest(owner_path)!=owner['sha256'] or owner_path.stat().st_size!=owner['bytes']:raise ValueError('Owner receipt differs')
 service_path,components['service']=input_artifact(supervisor,'service','wireless-remote-service.arm')
 service_receipt,service=receipt(service_path.parent/'build.json')
 if not service.get('built') or digest(service_path)!=service['sha256']:raise ValueError('Service receipt differs')
 config_path,components['configuration']=input_artifact(supervisor,'config','config.bin')
 config=config_path.read_bytes()
 if len(config)!=80 or config[:8] not in (b'XWRUN001',b'XWRUN002'):raise ValueError('Configuration format mismatch')
 synthetic=config[32:64]==bytes(range(1,33)) or config[24:30]==bytes([2,1,2,3,4,5])
 components['host_library']=artifact(host_path.parent/'libx1000-player-analysis.so',host['library_sha256'],host['library_bytes'])
 stock=ROOT/'work/targets-jp/SpiderApp'
 if digest(stock)!=host['stock_sha256']:raise ValueError('Original player differs')
 player=host_path.parent/'SpiderApp.player-prepare.analysis-only.elf'
 components['player_elf']=artifact(player,host['candidate_sha256'],stock.stat().st_size+host['candidate_growth_bytes'])
 system_delta=host['candidate_growth_bytes']+components['host_library']['bytes']+components['supervisor']['bytes']
 report=dict(passed=True,analysis_only=True,ready_to_run_on_device=False,ready_to_flash=False,
  firmware_package_created=False,installation_files_generated=False,device_accessed=False,
  project_version=(ROOT/'VERSION').read_text().strip(),components=components,
  receipts={role:dict(local=path.relative_to(ROOT).as_posix(),sha256=digest(path)) for role,path in
            [('host',host_path),('supervisor',supervisor_path),('owner',owner_receipt),('service',service_receipt)]},
  configuration_kind='synthetic-fixture' if synthetic else 'unqualified-private',sensitive_fields_recorded=False,
  core_system_file_payload_delta_bytes=system_delta,
  external_core_payload_bytes=sum(components[name]['bytes'] for name in ('owner','service','configuration')),
  radio_dependencies=radio_dependencies(owner),
  whole_image_capacity_checked=False,physical_partition_margin_verified=False,
  limitations=['Component identity review only; no boot/install overlay, updater or UPG is generated.',
   'Core payload delta excludes localization/menu resources, launch wrapper, filesystem allocation and bad blocks.',
   'Owner driver/context/session-key/packet-number dependencies remain outside this inventory; never replace persistent PN journals with seeds.',
   'Configuration is not hardware-paired or qualified; a synthetic fixture must not be presented as a device package.',
   'Sustained RF, audio/latency, standby, sleep/wake and USB ownership still require physical acceptance.'])
 out=WORK/'managed-remote-profile-review'/str(time.time_ns());out.mkdir(parents=True)
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 (WORK/'managed-remote-profile-review-latest.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,review=(out/'review.json').relative_to(ROOT).as_posix(),configuration_kind=report['configuration_kind'],core_system_file_payload_delta_bytes=system_delta,ready_to_flash=False),indent=2))
if __name__=='__main__':main()
