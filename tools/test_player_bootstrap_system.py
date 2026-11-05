"""Opt-in exec bootstrap preserves process identity with original Sony loader."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
from app_registry import ROOT
from build_player_host import build
from player_arm_guest import stock_libraries,run_guest
managed='--managed-host' in sys.argv
builtin='--builtin-localization' in sys.argv
native_settings='--native-remote-settings' in sys.argv
review_arg=sys.argv[sys.argv.index('--host-review')+1] if '--host-review' in sys.argv else None
layout_arg=sys.argv[sys.argv.index('--layout-review')+1] if '--layout-review' in sys.argv else None
if layout_arg and not review_arg:raise ValueError('Layout execution requires reviewed host')
if review_arg:managed=builtin=native_settings=True
if native_settings:builtin=True
if builtin and not managed:raise ValueError('Built-in localization requires --managed-host')
name='player-bootstrap-managed-system' if managed else 'player-bootstrap-system'
if builtin:name+='-builtin-language'
if native_settings:name+='-native-settings'
if review_arg:name+='-review-'+str(time.time_ns())
w=ROOT/'work'/name;w.mkdir(exist_ok=True);libraries=stock_libraries(include_rt=True,include_dl=True)
if review_arg:
 from review_managed_remote_profile import receipt,artifact,private
 hp,host_report=receipt(review_arg);service=hp.parent/'libx1000-player-analysis.so'
 artifact(service,host_report['library_sha256'],host_report['library_bytes'])
else:service,_,host_report=build(managed_host=managed,engine_provider=managed,native_prepare=managed,builtin_localization=builtin,native_remote_settings=native_settings)
libraries['libx1000-player.so']=service
startup=['runtime/store/start.c','runtime/store/start.S']
source='runtime/platform/player/bootstrap.c';probe_source='tools/fixtures/player_bootstrap_payload.c';init_source='tools/fixtures/player_bootstrap_init.c';marker_source='tools/fixtures/player_bootstrap_marker.c'
flags=['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none,-Ttext-segment=0x01000000','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
links=[str(libraries[n]) for n in ('libc.so.6','ld-linux.so.3')]
wrapper=w/'bootstrap.arm';missing=w/'bootstrap-missing-library.arm';default=w/'SpiderApp.bootstrap.analysis-only.arm';probe=w/'payload.arm';init=w/'init.arm';marker=w/'original-marker.so'
for output,extra in ((wrapper,['-DXW_PLAYER_PAYLOAD="/payload/SpiderApp"','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"']),(missing,['-DXW_PLAYER_PAYLOAD="/payload/SpiderApp"','-DXW_PLAYER_LIBRARY="/lib/absent-player.so"']),(default,[])):
 subprocess.run([*flags,*extra,source,*startup,*links,'-lgcc','-o',str(output)],cwd=ROOT,check=True)
startup_fallback=w/'startup-fallback.arm'
system=w/'system-preload.arm'
subprocess.run([*flags,'-DXW_PLAYER_SYSTEM_PRELOAD','-DXW_PLAYER_ARGV0="SpiderApp"','-DXW_PLAYER_PAYLOAD="/payload/SpiderApp"','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"',source,*startup,*links,'-lgcc','-o',str(system)],cwd=ROOT,check=True)
if layout_arg:
 lp,layout=receipt(layout_arg)
 if layout['host_build']['library_sha256']!=host_report['library_sha256']:raise ValueError('Layout/host mismatch')
 wrapper_name=layout.get('bootstrap_path','usr/local/libexec/x1000-player-start')
 if wrapper_name not in ('usr/local/bin/SpiderApp','usr/local/libexec/x1000-player-start'):raise ValueError('Unexpected system wrapper path')
 system=private(lp.parent/'root-overlay'/wrapper_name)
 row=layout['files'][wrapper_name];artifact(system,row['sha256'],row['bytes'])
once=w/'once-wrapper.arm'
subprocess.run([*flags,'-DXW_PLAYER_PAYLOAD="/payload/SpiderApp"','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"','-DXW_PLAYER_ONCE_TARGET="/bind/SpiderApp"','-DXW_PLAYER_ONCE_SOURCE="/bind/once-wrapper"',source,*startup,*links,'-lgcc','-o',str(once)],cwd=ROOT,check=True)
startup_sources=['runtime/platform/player/startup_delivery.c','runtime/store/deadline.c']
subprocess.run([*flags,'-DHB_STORE_LIBC_CLOCK','-DXW_PLAYER_PAYLOAD="/payload/SpiderApp"','-DXW_PLAYER_LIBRARY="/lib/libx1000-player.so"','-DXW_PLAYER_STARTUP_DIRECTORY="/tmp/x1000-player-bootstrap"','-DXW_PLAYER_STARTUP_NONCE="0123456789abcdef0123456789abcdef"','-DXW_PLAYER_STARTUP_GENERATION=23','-DXW_PLAYER_STARTUP_GRANTS=1','-DXW_PLAYER_FALLBACK="/payload/SpiderApp"',source,*startup_sources,*startup,str(libraries['librt.so.1']),str(libraries['libpthread.so.0']),*links,'-lgcc','-o',str(startup_fallback)],cwd=ROOT,check=True)
subprocess.run([*flags,probe_source,*startup,str(libraries['libdl.so.2']),*links,'-lgcc','-o',str(probe)],cwd=ROOT,check=True)
subprocess.run([*flags,'-DHB_STORE_LIBC_CLOCK',*(['-DHB_TEST_MANAGED'] if managed else []),*(['-DXW_LAYOUT_SYSTEM'] if layout_arg else []),init_source,*startup_sources,*startup,str(libraries['librt.so.1']),str(libraries['libpthread.so.0']),*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-shared','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',marker_source,'-o',str(marker)],cwd=ROOT,check=True)
libraries['original-marker.so']=marker
files={'bin/SpiderApp':wrapper,'missing/SpiderApp':missing,'payload/SpiderApp':probe,'bind/SpiderApp':probe,'startup/SpiderApp':startup_fallback,'once/SpiderApp':once,'system/SpiderApp':system}
if layout_arg:files.update({layout.get('player_payload_path','usr/local/bin/SpiderApp'):probe,'usr/local/lib/libx1000-player.so':service})
report=run_guest(w,init,files,libraries,['PLAYER_BOOTSTRAP_CASE=9 STATUS=0','PLAYER_VOLATILE_BIND_RESTORED','PLAYER_BOOTSTRAP_RENDEZVOUS_PASS','PLAYER_BOOTSTRAP_SELF_DETACH_PASS','PLAYER_BOOTSTRAP_SYSTEM_PASS'])
report.update(reviewed_host_used=bool(review_arg),exact_layout_wrapper_used=bool(layout_arg),stock_player_body_modeled=True)
inputs=startup+startup_sources+[source,probe_source,init_source,marker_source,'runtime/platform/player/startup_delivery.h',Path(__file__).relative_to(ROOT).as_posix()]
report.update(analysis_only=True,ready_to_flash=False,firmware_package_created=False,original_sony_loader=True,production_default_wrapper_bytes=default.stat().st_size,production_default_wrapper_sha256=hashlib.sha256(default.read_bytes()).hexdigest(),service_library_sha256=host_report['library_sha256'],cases=['default off','enabled with no prior preload','enabled preserving original preload and absolute argv0','explicitly disabled preserving original preload','missing service library preserves old preload and executes payload'],pid_argv_comm_cwd_env_preserved=report['passed'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs},limits=['Original Sony loader/libc and full service DSO execute under a generic ARM kernel; the payload is a C identity probe, not SpiderApp.','This tests environment/exec invariants and ordinary-PID pass-through, not AppList registration, full original GUI startup, sleep/USB or physical hardware.','No rootfs, AppList, boot script, device files or firmware installer is changed; production default paths are compiled only.'])
report['managed_host_profile']=managed;report['startup_rendezvous_and_exec_pass']=report['passed']
report['localization_profile']=host_report['localization_profile']
report['candidate_sha256']=host_report['candidate_sha256']
report['native_remote_settings_request_bridge']=native_settings
report['volatile_file_bind_and_unmount']=report['passed'];report['cases'].append('volatile file bind executes wrapper, unmount restores byte-identical target')
report['cases'].append('startup rendezvous absent: original fallback without service preload')
report['cases'].append('startup rendezvous succeeds: explicit descriptor and grant survive exec and managed constructor adopts it')
report['cases'].append('one-shot wrapper verifies own bytes and mount, detaches overlay before exec; original target is restored')
report['cases'].append('system preload loads the SDK independently of service opt-in and removes inherited one-shot grants')
report['limits'].append('Bind/unmount runs in guest RAM filesystem; Sony kernel, active executable mappings and physical cleanup remain unqualified.')
report['review_directory']=w.relative_to(ROOT).as_posix()
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if not review_arg:print((w/'serial.log').read_text(errors='replace')[-1600:])
print(json.dumps(report,indent=2));assert report['passed'],(w/'qemu.log').read_text(errors='replace')[-1000:]
