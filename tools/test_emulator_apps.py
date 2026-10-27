"""Offline core, touch, ABI and missing-storage lifecycle checks. No ROM downloads."""
from pathlib import Path
import subprocess,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/emulator-app-tests';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';rows=[]
core=['runtime/apps/emulators/gbc_core.c','runtime/native/sha256.c']+['third_party/gnuboy/'+n+'.c'for n in ['lcd','refresh','lcdc','palette','cpu','mem','rtc','hw','sound']]
touch=['tools/test_emulator_touch.c','runtime/apps/emulators/platform.c','runtime/native/frontend.c']
tama=['tools/test_tama_core.c','tools/fixtures/tama_memory_platform.c','third_party/tama-id/color.c','third_party/tama-id/core/tc_all.c']
proc_fixture=w/'proc-fixture';proc_fixture.mkdir(exist_ok=True)
for pid,fd,target,exe in [(100,3,'/dev/sound/dsp','/usr/local/bin/SpiderApp'),(101,4,'/dev/dsp0','/usr/local/bin/appproxy'),(102,5,'/dev/sound/mixer','/usr/local/bin/sysmgrd')]:
 folder=proc_fixture/str(pid);(folder/'fd').mkdir(parents=True,exist_ok=True)
 for name,destination in [('fd/'+str(fd),target),('exe',exe)]:
  p=folder/name
  if not p.is_symlink():p.symlink_to(destination)
flags=['-std=c99','-O2','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-stack-protector','-D_DEFAULT_SOURCE','-DIS_LITTLE_ENDIAN','-DTC_HOST','-DA918_COLOR_MENU','-DA918_COLOR_PERF','-ffunction-sections','-fdata-sections','-Ithird_party/gnuboy','-Ithird_party/tama-id','-Ithird_party/tama-id/core']
for name,src in [('schedule',['tools/test_gbc_schedule.c']),('owners',['tools/test_pcm_owner.c','runtime/apps/diagnostics/pcm_owner.c']),('gbc',['tools/test_emulator_cores.c']+core),('touch',touch),('volume',['tools/test_gbc_volume.c','runtime/apps/emulators/platform.c','runtime/native/frontend.c']),('tama',tama),('pcm',['tools/test_gbc_pcm.c','runtime/platform/pcm_output.c','runtime/apps/fm-radio/fm_audio.c'])]:
 for arm in [False,True]:
  out=w/(name+('-arm'if arm else '-host'));cmd=['arm-linux-gnueabi-gcc'if arm else'gcc',*flags,*src,'-Wl,--gc-sections','-o',str(out)]
  if arm:cmd+=['-march=armv5te','-marm','-mfloat-abi=soft','-nostdlib','-no-pie','-Wl,--hash-style=sysv','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
  built=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);assert built.returncode==0,built.stderr
  run=subprocess.run((['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]if arm else[])+[str(out)]+([str(proc_fixture)]if name=='owners'else[]),cwd=ROOT,capture_output=True,text=True,timeout=40);assert run.returncode==0,(name,arm,run.stdout,run.stderr);rows.append({'case':name,'ARM':arm,'stdout':run.stdout,'exit':run.returncode})
# Actual application renderer: native viewport, never nearest-neighbour expansion.
for tama in [False,True]:
 out=w/('render-tama'if tama else'render-gbc')
 subprocess.run(['gcc',*flags,*(['-DHB_TAMA_ID']if tama else[]),'-ffunction-sections','-fdata-sections','tools/test_emulator_render.c','runtime/apps/emulators/platform.c',*(['runtime/platform/pcm_output.c','runtime/apps/fm-radio/fm_audio.c']if not tama else[]),'-Wl,--gc-sections','-o',str(out)],cwd=ROOT,check=True)
 run=subprocess.run([str(out)],cwd=ROOT,capture_output=True,text=True,check=True);rows.append({'case':'actual-render-tama'if tama else'actual-render-gbc','stdout':run.stdout,'exit':run.returncode})
# Actual production apps: reject unverified storage, display error, touch-return releases devices.
src=(ROOT/'tools/fixtures/device_preload.c').read_text().replace('assert(touch&&timeout==50&&event<max_events())','assert(touch&&timeout==0&&event<max_events())');(w/'devices.c').write_text(src)
# Fixture include is repo-relative; copied fixture keeps its original font include semantics.
(w/'devices.c').write_text(src.replace('../../runtime/native/font.inc',str(ROOT/'runtime/native/font.inc')))
subprocess.run(['arm-linux-gnueabi-gcc','-D_GNU_SOURCE','-D_DEFAULT_SOURCE','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fPIC','-shared','-nostdlib','-Wl,--hash-style=sysv',str(w/'devices.c'),'runtime/native/syscalls.S',str(lib/'libc.so.6'),'-lgcc','-o',str(w/'devices.so')],cwd=ROOT,capture_output=True,check=True)
prefix=w/'sysroot';(prefix/'lib').mkdir(parents=True,exist_ok=True)
for n in ['libc.so.6','ld-linux.so.3']:shutil.copyfile(lib/n,prefix/'lib'/n)
for name in ['gbc','tamagotchi-id']:
 app=ROOT/'work/emulator-apps'/name/'package/app';frame=w/(name+'.rgb565');r=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-E','LD_PRELOAD='+str(w/'devices.so'),'-E','HB_TEST_FRAME='+str(frame),str(app)],cwd=ROOT,capture_output=True,text=True,timeout=20);assert r.returncode==0,(name,r.returncode,r.stderr);assert 'VDEV RELEASE COMPLETE'in r.stderr and 'VDEV UNMAP'in r.stderr;assert frame.stat().st_size==240*432*2;rows.append({'case':name+'-production-storage-rejection-and-touch-return','exit':r.returncode,'events':r.stderr.splitlines(),'app_sha256':hashlib.sha256(app.read_bytes()).hexdigest()})
# Packaged apps are recognized and executable hashes validate under the production launcher.
apps=w/'apps';apps.mkdir(exist_ok=True)
for name in ['gbc','tamagotchi-id']:shutil.copytree(ROOT/'work/emulator-apps'/name/'package',apps/name,dirs_exist_ok=True)
launcher=ROOT/'dist/0.1.0-dev.16/first-device-test-candidate8/02_PLAYER_FILES/HOMEBREW/launcher/app'
for command in ['--catalog','--check']:
 r=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),command,str(apps)],capture_output=True,text=True,timeout=15);assert r.returncode==0,(command,r.stdout,r.stderr);assert 'gbc'in r.stdout and 'tamagotchi-id'in r.stdout;rows.append({'case':command,'stdout':r.stdout,'exit':r.returncode})
report={'passed':True,'cases':rows,'scope':'Synthetic original test ROM only; host and real ARM core tests; virtual display/touch and missing /contents reject path. No real ROM, device audio, USB or hardware qualification.','hardware_tested':False}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
