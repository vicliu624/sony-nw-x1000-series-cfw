"""Build/test the offline FM review candidate. Never executes a native device mode."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from sdk_services import compiler as sdk_compiler
sdk_run = sdk_compiler(Path(__file__).resolve().parent)
from pathlib import Path
import hashlib, json, subprocess, struct, zlib, io, zipfile, shutil, sys
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[3]
work=ROOT/'work/fm-radio-review';work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
sdk_run([sys.executable,'tools/test_fm_storage.py'],cwd=ROOT,check=True)
flags=['-DHB_STORE_SONY_LIBC','-DHB_FM_VERSION="'+(ROOT/'runtime/apps/fm-radio/VERSION').read_text().strip()+'"','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
startup=['runtime/store/start.c','runtime/store/start.S']
library=[str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
tracked=set(startup+['docs/apps/FM_RADIO.md','tools/test_fm_storage.py','tools/fixtures/fm_storage.c','VERSION','runtime/apps/fm-radio/fm_storage.h','runtime/apps/fm-radio/fm_preferences.h','runtime/store/target_abi.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h','runtime/apps/fm-radio/fm_state.h','runtime/apps/fm-radio/fm_radio_skin.inc','runtime/native/linux_devices.h','runtime/native/linux_signals.h','runtime/native/frontend.h','runtime/native/linux_device_io.h','runtime/apps/fm-radio/fm_posix.h','runtime/apps/fm-radio/fm_session.h','runtime/apps/fm-radio/fm_audio.h','runtime/apps/fm-radio/fm_radio_ui.h','runtime/apps/fm-radio/fm_si470x.h','runtime/apps/fm-radio/fm_radio.h','runtime/native/font.inc'])
def build(name,sources,extra=()):
    tracked.update(sources);out=work/name
    sdk_run(['arm-linux-gnueabi-gcc',*flags,*extra,*sources,*startup,*library,'-o',str(out)],cwd=ROOT,check=True)
    return out
def run(path,args=(),code=0):
    p=sdk_run(base+[str(path),*args],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert p.returncode==code,(p.returncode,p.stdout,p.stderr)
    return p
core=['runtime/apps/fm-radio/fm_radio.c','runtime/apps/fm-radio/fm_radio_ui.c']
state=build('state-tests.arm',core+['runtime/apps/fm-radio/fm_state.c','tools/fixtures/fm_state.c']);run(state)
persistence=['runtime/apps/fm-radio/fm_state.c','runtime/apps/fm-radio/fm_storage.c','runtime/apps/fm-radio/fm_storage_native.c','runtime/apps/fm-radio/fm_preferences.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
wide=build('wideband-tests.arm',core+['runtime/apps/fm-radio/fm_state.c','tools/fixtures/fm_wideband.c']);run(wide)
native=['runtime/apps/fm-radio/fm_si470x.c','runtime/apps/fm-radio/fm_audio.c','runtime/apps/fm-radio/fm_session.c','runtime/apps/fm-radio/fm_posix.c']
session=build('session-tests.arm',core+['runtime/apps/fm-radio/fm_si470x.c','runtime/apps/fm-radio/fm_audio.c','runtime/apps/fm-radio/fm_session.c','tools/fixtures/fm_session.c']);run(session)
audio=build('audio-tests.arm',['runtime/apps/fm-radio/fm_audio.c','tools/fixtures/fm_audio.c']);run(audio)
tuner=build('tuner-tests.arm',core+['runtime/apps/fm-radio/fm_si470x.c','tools/fixtures/fm_si470x.c']);run(tuner)
controller=build('controller-tests.arm',core+['tools/fixtures/fm_radio_ui.c']);run(controller)
model=build('model-tests.arm',core+['tools/fixtures/fm_radio.c']);run(model)
native_app=build('native-app-tests.arm',core+native+persistence+['runtime/apps/fm-radio/fm_radio_app.c','runtime/native/frontend.c','tools/fixtures/fm_native_app.c'],['-DHB_FM_APP_TEST','-Wl,--wrap=fm_storage_open']);run(native_app)
ui=build('ui-tests.arm',core+native+persistence+['runtime/apps/fm-radio/fm_posix_io.c']+['runtime/apps/fm-radio/fm_radio_app.c','runtime/native/frontend.c','tools/fixtures/fm_radio_app.c'],['-DHB_FM_APP_TEST']);run(ui)
# Render the actual C framebuffer captured by the virtual UI fixture.
def chunk(kind,payload):
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
for name in ['main','tuning','favorites','results','keypad','pressed','error','native-main']:
    raw=(work/(name+'.rgb565')).read_bytes();assert len(raw)==240*432*2
    rgb=bytearray()
    for y in range(432):
        rgb.append(0)
        for x in range(240):
            pixel=struct.unpack_from('<H',raw,(y*240+x)*2)[0]
            rgb.extend((((pixel>>11)&31)*255//31,((pixel>>5)&63)*255//63,(pixel&31)*255//31))
    (work/(name+'.png')).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rgb))+chunk(b'IEND',b''))
app=build('fm-radio.arm',core+native+persistence+['runtime/apps/fm-radio/fm_posix_io.c']+['runtime/apps/fm-radio/fm_radio_app.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c'])
undefined=subprocess.check_output(['arm-linux-gnueabi-nm','-u',str(app)],text=True)
assert '__ioctl_time64' not in undefined and ' ioctl' in undefined
assert 'simulated' in run(app,['--help']).stdout
assert 'no device access' in run(app,['--selftest']).stdout
assert run(app,['--version']).stdout.strip()==(ROOT/'runtime/apps/fm-radio/VERSION').read_text().strip()
assert 'Usage:' in run(app,['--invalid'],code=64).stderr
report={'passed':True,'software_complete':False,'hardware_tested':False,'ready_to_flash':False,'native_reception_code_implemented':True,'hardware_reception_verified':False,'native_adapter_and_ui_wired':True,'native_cli_enabled':True,'physical_device_execution_performed':False,'artifact':str(app.relative_to(ROOT)),'sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'fm_band_khz':[76000,108000],'restores_original_tuner_config':True,'checks':['Wide FM: numeric108MHz,108.1 rejection,321-step full scan, above90MHz stations/save, band config write/readback/rollback/restoration','Native app CLI plus real PC storage: save, restart restore, failed storage lease, restart preserves old state','ARM926 state codec: round trip, CRC/truncation rejection, range/UTF8/duplicate validation','ARM926 native adapter and graphical app with fake OS operations: fourteen startup/interaction/stop/failure/persistence cases including rendered startup error','ARM926 session: muted startup, C tuner adapter via UI and fake ioctl, scan mute/resume, tuning-error mute, scan teardown, staged failures, quiesce/restore retries and close failures','ARM926 audio tests: muted preparation, tuner route, PCM silence, snapshot/restore, partial failures, internal-mute mismatch, retry and no analog volume change','ARM926 controller tests: decimal MHz entry, invalid input, favorite pagination/delete/select, scan result selection, scanning restrictions','ARM926 tuner tests: identity, wire ABI, units, band/spacing, completion/channel, timeout, cancel, read/write failures','ARM926 model tests: band/grid rejection, wrap, bounded favorites, rename, cancel, successful scan, sample/tune/restore errors, transactional scan results','ARM926 UI tests with fake display/touch: tap/back, open failure, stop, device error, close error','Actual candidate links stock ioctl without time64 and runs safe help/version/selftest/invalid-argument entries only'],'limits':['Only --demo has a synthetic tuner; not reception evidence.','Tuner/audio/session adapters are tested through fake transports. Wide-band software paths tested; physical RF range, audio and hardware handoff are not qualified. Native review entry is compiled and tested only with fake OS/device operations.','Independent native application entry enabled; no device execution or installation was performed.'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(tracked|{'tools/build_fm_radio.py'})}}

version=(ROOT/'runtime/apps/fm-radio/VERSION').read_text().strip()
package_root=work/'package';folder=package_root/'HOMEBREW/apps/fm-radio';folder.mkdir(parents=True,exist_ok=True)
packaged=folder/'app';shutil.copyfile(app,packaged);data=packaged.read_bytes()
manifest=('api=1\nid=fm-radio\nname=Pocket FM\nversion='+version+'\ntarget=sony-nw-x1000-jp\nexec=app\nbytes='+str(len(data))+'\nsha256='+hashlib.sha256(data).hexdigest()+'\n').replace('\n','\n')
(folder/'app.ini').write_text(manifest)
index='HBFILES1\n'+''.join(hashlib.sha256(p.read_bytes()).hexdigest()+' '+str(p.stat().st_size)+' '+p.name+'\n'for p in [packaged,folder/'app.ini'])
(folder/'files.sha256').write_text(index)
launcher=ROOT/'work/libc-launcher-review/launcher.elf'
checked=sdk_run(base+[str(launcher),'--check',str(package_root/'HOMEBREW/apps')],cwd=ROOT,capture_output=True,text=True,timeout=15)
assert checked.returncode==0 and checked.stdout=='fm-radio VERIFIED\n',checked

# Independent package checks: stock loader dependencies, exact file inventory,
# every file's size/hash, and the native launcher discovery contract.
assert {p.name for p in folder.iterdir()}=={'app','app.ini','files.sha256'}
elf=ELFFile(io.BytesIO(data))
needed=[tag.needed for tag in elf.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_NEEDED']
assert needed==['libc.so.6']
for line in (folder/'files.sha256').read_text().splitlines()[1:]:
 digest,size,name=line.split(' ');item=folder/name
 assert item.stat().st_size==int(size) and hashlib.sha256(item.read_bytes()).hexdigest()==digest
report['package_verified']=True
report['package_manifest']=str((folder/'app.ini').relative_to(ROOT))
report['needed']=needed
report['checks'].append('Native launcher verifies package discovery, executable size/SHA256 and ELF; resource inventory independently checked')
storage=json.loads((ROOT/'work/fm-storage-tests/report.json').read_text());assert storage['passed']
report['checks'].extend(storage['checks'])
for name,digest in storage['sources'].items():
 assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
 report['sources'][name]=digest
report['sources']['tools/build_fm_radio.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['software_complete']=True
report['qualification']='Software implementation and PC acceptance complete; hardware validation pending'
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
readme=(ROOT/'docs/apps/FM_RADIO.md').read_bytes()
notice=b'Local experimental development package. No Sony firmware, original libraries or product images are bundled. Existing source notices apply; this package grants no new blanket source license. Hardware validation is pending.\n'
files={
 'README.md':readme,
 'NOTICE.txt':notice,
 'build.json':(work/'build.json').read_bytes(),
 'storage-tests.json':(ROOT/'work/fm-storage-tests/report.json').read_bytes(),
}
for name in ['app','app.ini','files.sha256']:files['HOMEBREW/apps/fm-radio/'+name]=(folder/name).read_bytes()
for name in sorted(report['sources']):files['source/'+name]=(ROOT/name).read_bytes()
for name in ['tuning','favorites','keypad','error']:files['preview/'+name+'.png']=(work/(name+'.png')).read_bytes()
archive=work/('Pocket-FM-'+version+'-experimental.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name,content in sorted(files.items()):
  assert not name.startswith('/') and '..' not in name.split('/')
  info=zipfile.ZipInfo(name,(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,content)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and set(z.namelist())==set(files)
 for name,content in files.items():assert z.read(name)==content
summary={'software_complete':True,'package':str(archive.relative_to(ROOT)),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,'native_cli_enabled':True,'fm_band_khz':[76000,108000],'hardware_tested':False,'player_written':False,'firmware_created':False}
(work/'package.json').write_text(json.dumps(summary,indent=2)+'\n')
(work/'SHA256SUMS').write_text(summary['sha256']+'  '+archive.name+'\n')
print(json.dumps(summary,indent=2))
