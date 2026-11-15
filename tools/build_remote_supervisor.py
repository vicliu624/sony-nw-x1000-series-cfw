"""Build the Remote supervisor from reviewed executable inputs, PC only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from app_registry import ROOT
from component_receipts import component_build, digest, private
from evidence_checks import gcc_project_dependencies
from player_arm_guest import stock_libraries
from sdk_build import fresh_work


CHILDREN = {'owner': 'remote-rf-owner.arm', 'service': 'wireless-remote-service.arm'}


def build(*, review=None, service_review=None, shared_wifi_owner_review=None, output=None,
          reusable_sessions=False, forward_owner_mode_view=False, device_pairing=False,
          embedded_runtime=False, play_mode_control=False):
 if play_mode_control and not (device_pairing and reusable_sessions and forward_owner_mode_view):
  raise ValueError('--play-mode-control requires the managed device-pairing profile')
 if embedded_runtime and not device_pairing:
  raise ValueError('--embedded-runtime requires --device-pairing')
 if device_pairing and not (reusable_sessions and forward_owner_mode_view):
  raise ValueError('--device-pairing requires managed reusable sessions and a forwarded owner view')
 review_path = None
 components = {}
 if review is None:
  if not (embedded_runtime and shared_wifi_owner_review and service_review):
   raise ValueError('Embedded review builds require --shared-wifi-owner-review and --service-review')
  components = {
   'owner': component_build(shared_wifi_owner_review, CHILDREN['owner']),
   'service': component_build(service_review, CHILDREN['service']),
  }
  _, owner, owner_input = components['owner']
  _, service, service_input = components['service']
  if any(component.get('fixture_only') or not component.get('original_libc_arm_entry_checks')
         for component in (owner, service)):
   raise ValueError('Embedded components require original-libc build checks')
  if (owner.get('finite_owner') is not False or not owner.get('owner_mode_view_required')
      or not owner.get('root_cold_supported') or owner.get('data_directory') != '/contents/HOMEBREW/data/wireless-remote'):
   raise ValueError('Expected a managed Root owner for the Wireless Remote data directory')
  review = dict(device_directory=owner['data_directory']+'/runtime',
                owner_mode_view_supported=owner.get('owner_mode_view_supported'),
                generation=None, files={'owner': owner_input, 'service': service_input})
 else:
  if service_review:
   raise ValueError('--service-review is for builds using component receipts directly')
  review_path = private(review)
  review = json.loads(review_path.read_text(encoding='utf-8'))
 directory = review['device_directory']
 if forward_owner_mode_view and review.get('owner_mode_view_supported') is not True:
  raise ValueError('Reviewed owner must support mode-view FD entry')
 if not (directory=='/contents/HOMEBREW/data/wireless-remote/runtime' or
         re.fullmatch(r'/contents/HOMEBREW/data/player-sdk-live-[0-9]+/remote',directory)):
  raise ValueError('Unexpected Remote runtime directory')
 for role,leaf in CHILDREN.items():
  row=review['files'][role]
  local=private(row['local'].replace('\\','/'))
  if role not in components:
   components[role]=component_build(local.parent/'build.json',leaf)
  _, component, identity=components[role]
  if identity!=dict(local=local.relative_to(ROOT).as_posix(),bytes=row['bytes'],sha256=row['sha256']):
   raise ValueError('Launch review does not match the reviewed '+role+' executable')
  if role=='service' and play_mode_control and component.get('command_negotiation_supported') is not True:
   raise ValueError('Mode control requires a matching service with explicit command negotiation')
 out = fresh_work(output or ROOT/'work/remote-supervisor-build'/str(time.time_ns()))
 header=[];inputs=['tools/build_remote_supervisor.py','runtime/apps/wireless-remote/run_profile.h','runtime/apps/wireless-remote/startup_result.h'];rows={};local_rows={};mode_host_snapshot=None
 if play_mode_control:header.append('#define WR_PLAY_MODE_CONTROL 1')
 inputs+=['runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h']
 shared_owner_review=None;shared_wifi_radio_sha256=None
 root_cold_supported=False
 if shared_wifi_owner_review:
  owner_path,owner,owner_identity=components['owner']
  if private(shared_wifi_owner_review)!=owner_path:
   owner_path,owner,owner_identity=component_build(shared_wifi_owner_review, CHILDREN['owner'])
  expected=review['files']['owner']
  if (not forward_owner_mode_view or not reusable_sessions or not owner.get('shared_wifi_supported') or
      owner['data_directory']+'/runtime'!=directory or owner_identity['sha256']!=expected['sha256'] or owner_identity['bytes']!=expected['bytes']):
   raise ValueError('Shared Wi-Fi owner receipt does not match launch profile')
  shared_owner_review=owner_path.relative_to(ROOT).as_posix();inputs.append(shared_owner_review)
  inputs.append(owner_identity['local'])
  shared_wifi_radio_sha256=owner['candidate_sha256']
  root_cold_supported=bool(owner.get('root_cold_supported'))
  if root_cold_supported:header.append('#define WR_ROOT_COLD_OWNER 1')
 if device_pairing:header.append('static const char remote_config_path[]='+json.dumps(directory+'/config.bin')+';')
 elif reusable_sessions:header.append('static const uint64_t remote_template_generation='+str(review['generation'])+'ULL;')
 for name,leaf in [('service','service.arm'),('owner','owner.arm'),('config','config.bin')]:
  if name=='config' and device_pairing:continue
  row=review['files'][name]
  local=private(row['local'].replace('\\','/'))
  size,sha=row['bytes'],row['sha256']
  if name=='config':
   data=local.read_bytes()
   if hashlib.sha256(data).hexdigest()!=sha or len(data)!=size:
    raise ValueError('Launch configuration identity differs')
   assert len(data)==80 and data[:8] in (b'XWRUN001',b'XWRUN002') and int.from_bytes(data[8:16],'little')==review['generation']
   if data[:8]==b'XWRUN002':
    assert review.get('play_mode_host_supported') is True,'Mode profile requires an explicitly supported host'
    host_path=(ROOT/review['host_review'].replace('\\','/')).resolve();assert host_path.is_relative_to(ROOT/'work')
    host=json.loads(host_path.read_text(encoding='utf-8'))
    if 'host_build' in host:
     assert host['host_build'].get('play_mode_read_supported') is True,'Selected host has no native mode reader'
     library=host_path.parent/'files/sdk/libx1000-player.so'
     assert hashlib.sha256(library.read_bytes()).hexdigest()==host['host_build']['library_sha256']==host['files']['sdk/libx1000-player.so']['sha256'],'Host library identity mismatch'
     assert host['generation']==review['generation'] and host['grants']&1,'Mode host generation/grant mismatch'
    else:
     from remote_host_review import mode_host
     assert reusable_sessions,'Native host requires runtime session generation'
     mode_host(host_path)
     snapshot=out/'mode-host-review';snapshot.mkdir()
     for filename in ('build.json','libx1000-player-analysis.so'):
      shutil.copy2(host_path.parent/filename,snapshot/filename)
     mode_host(snapshot/'build.json')
     mode_host_snapshot=(snapshot/'build.json').relative_to(ROOT).as_posix()
     inputs+=['tools/remote_host_review.py',mode_host_snapshot,(snapshot/'libx1000-player-analysis.so').relative_to(ROOT).as_posix()]
   assert int.from_bytes(data[16:24],'little') and any(data[24:30]) and not data[24]&1 and data[30:32]==b'\0\0' and any(data[32:64]) and any(data[64:80])
  device_path='/usr/local/libexec/x1000-remote-'+leaf if embedded_runtime else directory+'/'+leaf
  header.append('static const struct wr_launch_input remote_'+name+'_input={'+json.dumps(device_path)+','+str(size)+',{'+','.join(str(x) for x in bytes.fromhex(sha))+'}};')
  rows[name]=dict(path=device_path,bytes=size,sha256=sha)
  local_rows[name]=dict(local=local.relative_to(ROOT).as_posix(),bytes=size,sha256=sha)
 inputs.extend(path.relative_to(ROOT).as_posix() for path,_,_ in components.values())
 (out/'remote_launch_inputs.h').write_text('\n'.join(header)+'\n',encoding='utf-8')
 sources=['runtime/apps/wireless-remote/supervisor.c','runtime/apps/wireless-remote/run_profile.c','runtime/platform/player/startup_delivery.c',
          'runtime/platform/services/descriptor.c','runtime/platform/espnow/xnow_file_check.c',
          'runtime/platform/espnow/xnow_handoff.c','runtime/native/sha256.c','runtime/store/deadline.c',
          'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
 if device_pairing:
  sources+=['runtime/apps/wireless-remote/pairing_store.c']
  inputs+=['runtime/apps/wireless-remote/pairing_store.h']
 libs=stock_libraries(include_rt=True);artifact=out/'remote-supervisor.arm'
 compiler=['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                 '-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK',*(['-DWR_REUSABLE_SESSIONS'] if reusable_sessions else []),*(['-DWR_OWNER_MODE_VIEW'] if forward_owner_mode_view else []),*(['-DWR_DEVICE_PAIRING'] if device_pairing else []),*(['-DWR_EMBEDDED_RUNTIME'] if embedded_runtime else []),'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                 '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
                 '-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none','-I'+str(out)]
 inputs += [*[row['local'] for row in local_rows.values()], 'tools/evidence_checks.py',
            'tools/component_receipts.py']
 if review_path:
  inputs.append(review_path.relative_to(ROOT).as_posix())
 dependencies=gcc_project_dependencies(ROOT, compiler, sources)
 source_hashes={p:digest(ROOT/p) for p in sorted(dependencies.union(inputs))}
 libraries=[libs[name] for name in ('librt.so.1','libpthread.so.0','libc.so.6','ld-linux.so.3')]
 linked_hashes={p.relative_to(ROOT).as_posix():digest(p) for p in libraries}
 subprocess.run([*compiler,*sources,*map(str,libraries),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
 base=['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(artifact)]
 for argv,expected in [(['--help'],0),([],64),(['/tmp/invalid','00'*16,'23','--charger-confirmed','--exclusive-radio-confirmed'],64),(['--delivery-fd','0','23','--charger-confirmed','--exclusive-radio-confirmed'],64),(['--delivery-fd','65535','23','--charger-confirmed','--exclusive-radio-confirmed'],64)]:
  run=subprocess.run(base+argv,cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert run.returncode==expected,run.stdout+run.stderr
 if device_pairing:
  run=subprocess.run(base+['--pairing-radio','0','4','5','01'*16,'6','1','2','3'],cwd=ROOT,capture_output=True,text=True,timeout=10)
  assert run.returncode==64,run.stdout+run.stderr
  run=subprocess.run(base+['--pairing-store','forget','0'],cwd=ROOT,capture_output=True,text=True,timeout=10)
  assert run.returncode==64,run.stdout+run.stderr
  reader,writer=os.pipe()
  try:
   run=subprocess.run(base+['--pairing-store','query',str(writer)],cwd=ROOT,pass_fds=(writer,),capture_output=True,timeout=10)
   assert run.returncode==0 and os.read(reader,16)==b'WPS1\x02'+bytes(11),run.stderr
  finally:
   os.close(writer);os.close(reader)
 for name,expected in {**source_hashes,**linked_hashes}.items():
  if digest(ROOT/name)!=expected:
   raise ValueError('Remote supervisor input changed during build: '+name)
 report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,
             sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),original_libc_arm_entry_checks=True,
             private_launch_profile=True,reusable_sessions=reusable_sessions,device_accessed=False,radio_started=False,inputs=rows,
             owner_mode_view_forwarded=forward_owner_mode_view,
             device_pairing=device_pairing,
             embedded_runtime=embedded_runtime,
             play_mode_control=play_mode_control,
             root_cold_supported=root_cold_supported,
             shared_wifi_owner_review=shared_owner_review,
             shared_wifi_radio_sha256=shared_wifi_radio_sha256,
             launch_review=review_path.relative_to(ROOT).as_posix() if review_path else None,local_inputs=local_rows,
             mode_host_snapshot=mode_host_snapshot,
             generation=review['generation'],source_hashes=source_hashes,
             linked_library_hashes=linked_hashes,
             generated_header_sha256=hashlib.sha256((out/'remote_launch_inputs.h').read_bytes()).hexdigest())
 (out/'build.private.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 return artifact,report


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--review',type=Path,help='Legacy launch proposal for a finite or staged session')
 parser.add_argument('--service-review',type=Path,help='Service build.json for embedded builds using component receipts')
 parser.add_argument('--shared-wifi-owner-review',type=Path)
 parser.add_argument('--reusable-sessions',action='store_true')
 parser.add_argument('--forward-owner-mode-view',action='store_true')
 parser.add_argument('--device-pairing',action='store_true')
 parser.add_argument('--embedded-runtime',action='store_true')
 parser.add_argument('--play-mode-control',action='store_true')
 parser.add_argument('--output',type=Path)
 args=parser.parse_args()
 try:
  _,report=build(**vars(args))
 except (ValueError,OSError) as error:
  parser.error(str(error))
 print(json.dumps(report,indent=2))


if __name__=='__main__':
 main()
