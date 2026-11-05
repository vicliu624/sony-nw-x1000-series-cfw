"""Prepare private one-start validation files; never deploys, mounts or flashes."""
import argparse,contextlib,hashlib,io,json,os,re,runpy,secrets,subprocess,time
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--device-directory',required=True);p.add_argument('--reuse-private-review',type=Path);m=p.add_mutually_exclusive_group();m.add_argument('--volume-roundtrip',action='store_true');m.add_argument('--observe',action='store_true');m.add_argument('--remote',action='store_true');a=p.parse_args()
if not re.fullmatch(r'/contents/HOMEBREW/data/player-sdk-live-[0-9]+',a.device_directory):raise ValueError('Use the verified dedicated user-storage staging directory')
out=ROOT/'work/player-live-start'/str(time.time_ns());out.mkdir(parents=True)
base=ROOT/'work/external-language-bridge-10-process-cache-final/SpiderApp.external-language.analysis-only.elf'
if hashlib.sha256(base.read_bytes()).hexdigest()!='213c4c777ff8f71e400bc1287d1096307b7c3fc48122ca4c0d81a88fcfc712a6':raise ValueError('Pinned installed language-cache baseline required')
reused=None;probe=None
if a.reuse_private_review:
 if not a.remote:raise ValueError('Retained host reuse is restricted to the finite remote qualification')
 reused=a.reuse_private_review.resolve()
 if not reused.is_relative_to(ROOT/'work'):raise ValueError('Private input review must remain under work')
 prior=json.loads(reused.read_text());prior_files=reused.parent/'files'
 if not prior.get('prepared') or not prior.get('private_one_start_material'):raise ValueError('Not a prepared private review')
 for name in ('original/SpiderApp','sdk/SpiderApp','sdk/libx1000-player.so'):
  data=(prior_files/name).read_bytes();row=prior['files'][name]
  if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Retained material mismatch: '+name)
 if (prior_files/'original/SpiderApp').read_bytes()!=base.read_bytes():raise ValueError('Retained baseline mismatch')
 library=prior_files/'sdk/libx1000-player.so';payload=prior_files/'sdk/SpiderApp';host=prior['host_build']
else:
 from build_player_host import build
 with contextlib.redirect_stdout(io.StringIO()):
  library,payload,host=build(managed_host=True,engine_provider=True,native_prepare=True)
  if not a.remote:probe=runpy.run_path(str(ROOT/'tools/build_player_live_probe.py'))['artifact']
if host['candidate_sha256']!='227006483d65b7011ffcdc6fd84c8f303e4f1cb77ae443d8a5f417e40d11c688' or hashlib.sha256(payload.read_bytes()).hexdigest()!=host['candidate_sha256']:raise ValueError('Installed-base composition mismatch')
nonce=secrets.token_hex(16);generation=time.time_ns();ipc='/tmp/x1000-player-'+nonce[:16]
grants=3 if a.volume_roundtrip or a.remote else 1
files=out/'files'
for d in ('original','sdk','wrapper'): (files/d).mkdir(parents=True)
items={'original/SpiderApp':base,'sdk/SpiderApp':payload,'sdk/libx1000-player.so':library}
if probe:items['player-readonly-probe.arm']=probe
for name,source in items.items():
 target=files/name;target.write_bytes(source.read_bytes());target.chmod(0o644 if name.endswith('.so') else 0o755)
lib=stock_libraries(include_rt=True)
source='runtime/platform/player/bootstrap.c';extra=['runtime/platform/player/startup_delivery.c','runtime/store/deadline.c','runtime/store/start.c','runtime/store/start.S']
defines={'XW_PLAYER_PAYLOAD':a.device_directory+'/sdk/SpiderApp','XW_PLAYER_LIBRARY':a.device_directory+'/sdk/libx1000-player.so','XW_PLAYER_FALLBACK':a.device_directory+'/original/SpiderApp','XW_PLAYER_STARTUP_DIRECTORY':ipc,'XW_PLAYER_STARTUP_NONCE':nonce,'XW_PLAYER_ONCE_TARGET':'/usr/local/bin/SpiderApp','XW_PLAYER_ONCE_SOURCE':a.device_directory+'/wrapper/SpiderApp'}
flags=['-D'+k+'="'+v+'"' for k,v in defines.items()]+['-DXW_PLAYER_STARTUP_GENERATION='+str(generation)+'ULL','-DXW_PLAYER_STARTUP_GRANTS='+str(grants)]
wrapper=files/'wrapper/SpiderApp'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none,-Ttext-segment=0x01000000',*flags,source,*extra,str(lib['librt.so.1']),str(lib['libpthread.so.0']),str(lib['libc.so.6']),str(lib['ld-linux.so.3']),'-lgcc','-o',str(wrapper)],cwd=ROOT,check=True)
manifest={}
for f in sorted(files.rglob('*')):
 if f.is_file():manifest[f.relative_to(files).as_posix()]=dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),md5=hashlib.md5(f.read_bytes()).hexdigest())
report=dict(prepared=True,private_one_start_material=True,device_directory=a.device_directory,ipc_directory=ipc,nonce=nonce,generation=generation,grants=grants,read_only_probe=not a.volume_roundtrip and not a.remote,volume_roundtrip=a.volume_roundtrip,observe=a.observe,remote_qualification=a.remote,reused_host_review=str(reused.relative_to(ROOT)) if reused else None,files=manifest,host_build=host,source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [source,*extra,'tools/prepare_player_live_start.py']},device_accessed=False,activated=False,firmware_created=False,limits=['Whole remote lifecycle/RF hardware operation remains unqualified.','Retained host inputs preserve their original source/build identity; they are not a new host build.','Never publish: includes proprietary player binaries and a one-start private nonce.','Do not remove staged files while an executable is running from them or a transient overlay remains.'])
(out/'review.private.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'output':str(out.relative_to(ROOT)),'files':{k:v['bytes'] for k,v in manifest.items()},'total_user_storage_bytes':sum(v['bytes'] for v in manifest.values()),'activated':False,'firmware_created':False},indent=2))
