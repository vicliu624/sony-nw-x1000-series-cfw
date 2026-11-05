"""Build one private finite RF launch profile; never deploys, activates or flashes."""
import argparse,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=Path,required=True);parser.add_argument('--reusable-sessions',action='store_true');parser.add_argument('--forward-owner-mode-view',action='store_true');args=parser.parse_args()
review_path=args.review.resolve();assert review_path.is_relative_to(ROOT/'work')
review=json.loads(review_path.read_text(encoding='utf-8'));directory=review['device_directory']
if args.forward_owner_mode_view:assert review.get('owner_mode_view_supported') is True,'Reviewed owner must support mode-view FD entry'
assert directory=='/contents/HOMEBREW/data/wireless-remote/runtime' or re.fullmatch(r'/contents/HOMEBREW/data/player-sdk-live-[0-9]+/remote',directory)
out=ROOT/'work/remote-supervisor-build'/str(time.time_ns());out.mkdir(parents=True)
header=[];inputs=['tools/build_remote_supervisor.py','runtime/apps/wireless-remote/run_profile.h'];rows={};local_rows={};mode_host_snapshot=None
inputs+=['runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h']
if args.reusable_sessions:header.append('static const uint64_t remote_template_generation='+str(review['generation'])+'ULL;')
for name,leaf in [('service','service.arm'),('owner','owner.arm'),('config','config.bin')]:
 row=review['files'][name];local=(ROOT/row['local'].replace('\\','/')).resolve();assert local.is_relative_to(ROOT/'work')
 data=local.read_bytes();digest=hashlib.sha256(data).hexdigest();assert digest==row['sha256'] and len(data)==row['bytes']
 if name=='config':
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
    assert args.reusable_sessions,'Native host requires runtime session generation'
    mode_host(host_path)
    snapshot=out/'mode-host-review';snapshot.mkdir()
    for filename in ('build.json','libx1000-player-analysis.so'):
     shutil.copy2(host_path.parent/filename,snapshot/filename)
    mode_host(snapshot/'build.json')
    mode_host_snapshot=(snapshot/'build.json').relative_to(ROOT).as_posix()
    inputs+=['tools/remote_host_review.py','tools/review_managed_remote_profile.py',mode_host_snapshot,(snapshot/'libx1000-player-analysis.so').relative_to(ROOT).as_posix()]
  assert int.from_bytes(data[16:24],'little') and any(data[24:30]) and not data[24]&1 and data[30:32]==b'\0\0' and any(data[32:64]) and any(data[64:80])
 header.append('static const struct wr_launch_input remote_'+name+'_input={'+json.dumps(directory+'/'+leaf)+','+str(len(data))+',{'+','.join(str(x) for x in bytes.fromhex(digest))+'}};')
 rows[name]=dict(path=directory+'/'+leaf,bytes=len(data),sha256=digest)
 local_rows[name]=dict(local=local.relative_to(ROOT).as_posix(),bytes=len(data),sha256=digest)
(out/'remote_launch_inputs.h').write_text('\n'.join(header)+'\n',encoding='utf-8')
sources=['runtime/apps/wireless-remote/supervisor.c','runtime/apps/wireless-remote/run_profile.c','runtime/platform/player/startup_delivery.c',
         'runtime/platform/services/descriptor.c','runtime/platform/espnow/xnow_file_check.c',
         'runtime/platform/espnow/xnow_handoff.c','runtime/native/sha256.c','runtime/store/deadline.c',
         'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
libs=stock_libraries(include_rt=True);artifact=out/'remote-supervisor.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                '-DHB_STORE_SONY_LIBC','-DHB_STORE_LIBC_CLOCK',*(['-DWR_REUSABLE_SESSIONS'] if args.reusable_sessions else []),*(['-DWR_OWNER_MODE_VIEW'] if args.forward_owner_mode_view else []),'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector',
                '-nostdlib','-no-pie','-Wl,--hash-style=sysv,--build-id=none','-I'+str(out),*sources,
                str(libs['librt.so.1']),str(libs['libpthread.so.0']),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',':'.join(dict.fromkeys(str(p.parent) for p in libs.values())),str(artifact)]
for argv,expected in [(['--help'],0),([],64),(['/tmp/invalid','00'*16,'23','--charger-confirmed','--exclusive-radio-confirmed'],64),(['--delivery-fd','0','23','--charger-confirmed','--exclusive-radio-confirmed'],64),(['--delivery-fd','65535','23','--charger-confirmed','--exclusive-radio-confirmed'],64)]:
 run=subprocess.run(base+argv,cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert run.returncode==expected,run.stdout+run.stderr
inputs += [review_path.relative_to(ROOT).as_posix(),*[row['local'] for row in local_rows.values()]]
report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,
            sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),original_libc_arm_entry_checks=True,
            private_launch_profile=True,reusable_sessions=args.reusable_sessions,device_accessed=False,radio_started=False,inputs=rows,
            owner_mode_view_forwarded=args.forward_owner_mode_view,
            launch_review=review_path.relative_to(ROOT).as_posix(),local_inputs=local_rows,
            mode_host_snapshot=mode_host_snapshot,
            generation=review['generation'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+inputs},
            linked_library_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in libs.values()},
            generated_header_sha256=hashlib.sha256((out/'remote_launch_inputs.h').read_bytes()).hexdigest())
(out/'build.private.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
