"""Inspect a staged Remote profile without installing files."""
import argparse
import json
from pathlib import Path
import re
import time

# Keep the existing imports usable for research and inspection commands.
from component_receipts import (ROOT, WORK, artifact, component_build, digest,
                                native_sdk_build, private, receipt)
from player_remote_profile import input_artifact


def radio_dependencies(owner):
 """Inventory compiled immutable inputs without reading pairing keys or journals."""
 directory=owner['data_directory']
 if not re.fullmatch(r'/contents/HOMEBREW/data/[a-z][a-z0-9-]{0,47}',directory):raise ValueError('Invalid owner data directory')
 header=private(owner['exchange_header'])
 if digest(header)!=owner['exchange_header_sha256']:raise ValueError('Owner dependency header changed')
 text=header.read_text()
 rows=[]
 for path,size,raw in re.findall(r'\{"([^"\n]+)",(\d+),\{([0-9,]+)\}\}',text):
  values=bytes(int(value) for value in raw.split(','))
  if len(values)!=32 or path.rsplit('/',1)[0]!=directory+'/candidate':
   raise ValueError('Unexpected compiled radio dependency')
  rows.append(dict(device_path=path,bytes=int(size),sha256=values.hex(),storage='user-volume',device_presence_verified=False))
 if owner.get('external_radio_inputs_required') is False:
  if owner.get('root_cold_supported') is not True or text != 'static const struct stock_input exchange_inputs[]={\n};\n':
   raise ValueError('Expected an empty user-volume radio table for the Root owner')
 elif len(rows)!=2 or {row['device_path'].rsplit('/',1)[-1] for row in rows}!={'sd8686.bin','helper_sd.bin'}:
  raise ValueError('Incomplete compiled radio dependency inventory')
 return dict(immutable_inputs=rows,immutable_payload_bytes=sum(row['bytes'] for row in rows),
  pairing=dict(device_path=directory+'/session.keys',bytes=32,contents_read=False,paired_controller_verified=False),
  packet_numbers=dict(device_path=directory+'/pn',preserve_existing=True,seed_or_reset_permitted=False),
  compiled_header=dict(local=header.relative_to(ROOT).as_posix(),sha256=digest(header)),
  installation_complete=False)
def main():
 from sdk_build import fresh_work

 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--host-review',type=Path,required=True)
 parser.add_argument('--output',type=Path,help='New component review directory below work/')
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
 out=fresh_work(args.output or WORK/'managed-remote-profile-review'/str(time.time_ns()))
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,review=(out/'review.json').relative_to(ROOT).as_posix(),configuration_kind=report['configuration_kind'],core_system_file_payload_delta_bytes=system_delta,ready_to_flash=False),indent=2))
if __name__=='__main__':main()
