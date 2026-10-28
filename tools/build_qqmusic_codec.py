"""Offline pinned-source portable-C ARM codec build against original Sony libs."""
from pathlib import Path
import hashlib,json,subprocess,tarfile,sys
ROOT=Path(__file__).resolve().parents[1]
vendor=ROOT/'third_party/qqmusic-codecs';provenance=json.loads((ROOT/'sources/qqmusic-codec-sources.json').read_text())
for name,row in provenance['sources'].items():
    for path,record in row['files'].items():assert hashlib.sha256((vendor/name/path).read_bytes()).hexdigest()==record['vendored_sha256']
work=ROOT/'work/qqmusic-codec';work.mkdir(exist_ok=True)
live_session='--live-session' in sys.argv
device_app='--device-app' in sys.argv
audio_preview='--audio-preview' in sys.argv
assert not audio_preview or device_app
binding_import=live_session or device_app or '--binding-import' in sys.argv
job_import=binding_import or '--job-import' in sys.argv
network_import=job_import or '--network-import' in sys.argv
file_import=network_import or '--file-import' in sys.argv
if network_import:assert '--asan' not in sys.argv and '--host' not in sys.argv
suffix='binding-import-tests' if binding_import else ('job-import-tests' if job_import else ('network-import-tests' if network_import else ('file-import-tests' if file_import else 'codec-tests')))
build_name='build-binding-import.json' if binding_import else ('build-job-import.json' if job_import else ('build-network-import.json' if network_import else ('build-file-import.json' if file_import else 'build.json')))
if live_session:suffix='live-session';build_name='build-live-session.json'
if device_app:suffix='device-app';build_name='build-device-app.json'
wrap=['-Wl,--wrap=open,--wrap=open64,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=rename,--wrap=fsync'] if file_import else []
if device_app:wrap=['-Wl,--disable-new-dtags,-rpath,$ORIGIN/lib']
stb=ROOT/'third_party/qqmusic-stb';image_manifest=json.loads((ROOT/'sources/qqmusic-image-sources.json').read_text())
for name,digest in image_manifest['files'].items():assert hashlib.sha256((stb/name).read_bytes()).hexdigest()==digest
(work/build_name).unlink(missing_ok=True)
include=work/'include/ogg';include.mkdir(parents=True,exist_ok=True)
config='#ifndef QQ_OGG_TYPES\n#define QQ_OGG_TYPES\n#include <stdint.h>\ntypedef int16_t ogg_int16_t;\ntypedef uint16_t ogg_uint16_t;\ntypedef int32_t ogg_int32_t;\ntypedef uint32_t ogg_uint32_t;\ntypedef int64_t ogg_int64_t;\ntypedef uint64_t ogg_uint64_t;\n#endif\n'
(include/'config_types.h').write_text(config)
archive=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(archive,'r:gz') as packed:
    entries=[m for m in packed if m.isfile() and '/libm-' in m.name and m.name.endswith('.so')]
    assert len(entries)==1
    (work/'libm.so.6').write_bytes(packed.extractfile(entries[0]).read())
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
tremor=['mdct','block','window','synthesis','info','floor1','floor0','vorbisfile','res012','mapping0','registry','codebook','sharedbook']
shine=['bitstream','huffman','l3bitstream','l3loop','l3mdct','l3subband','layer3','reservoir','tables']
third=[vendor/'tremor'/(n+'.c') for n in tremor]+[vendor/'ogg/src/framing.c',vendor/'ogg/src/bitwise.c']+[vendor/'shine/src/lib'/(n+'.c') for n in shine]
own=['runtime/apps/qqmusic/qqmusic_import.c','runtime/apps/qqmusic/qqmusic_codec.c','tools/fixtures/qqmusic_codec.c','runtime/apps/qqmusic/qqmusic_qmc_codec.c','runtime/apps/qqmusic/qqmusic_qmc.c','runtime/apps/qqmusic/qqmusic_protocol.c','runtime/apps/qqmusic/qqmusic_session.c','runtime/apps/qqmusic/qqmusic_metadata.c','runtime/apps/qqmusic/qqmusic_id3.c','runtime/apps/qqmusic/qqmusic_image.c','runtime/apps/qqmusic/qqmusic_picture.c','runtime/native/sha256.c','runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
if file_import:
    own[2]='tools/fixtures/qqmusic_file_import.c'
    own+=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('file_import','mp3','publish','source','output','directory','stage','stage_volume','volume','storage','asset')]+['runtime/store/https_url.c']
network_libs=[];network_flags=[]
if network_import:
    resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
    own+=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('download','network','tls','response','cookie','http','json','credential','cgi','resource')]
    own+=['runtime/store/'+n+'.c' for n in ('resolver','connect_step','socket_step','tls_socket_step','deadline','tls_platform')]
    network_flags=['-DQQ_FILE_NETWORK','-DHB_STORE_LIBC_CLOCK','-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc')]
    network_libs=['-Wl,-rpath-link,'+str(resolver),str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1')]
if job_import:
    own[2]='tools/fixtures/qqmusic_job.c'
    own+=['runtime/apps/qqmusic/qqmusic_job.c','runtime/apps/qqmusic/qqmusic_journal.c','runtime/apps/qqmusic/qqmusic_worker.c','runtime/apps/qqmusic/qqmusic_export.c','runtime/native/linux_process_posix.c','runtime/native/linux_signals_posix.c']
    network_flags+=['-D_DEFAULT_SOURCE']
if binding_import:
    own+=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('stock_path','import_binding','entry_import','entry','program_import','program','identity','qimei','runtime','app','catalog','login','ui','devices','loop')]+['runtime/native/linux_devices.c','runtime/native/frontend.c']
    network_flags+=['-DQQ_JOB_BINDING']
if live_session:
    profile_dir=Path(sys.argv[sys.argv.index('--live-session')+1]).resolve()
    assert profile_dir.is_relative_to(ROOT/'work') and (profile_dir/'qqmusic_profile.h').is_file()
    own[2]='tools/fixtures/qqmusic_live_session.c'
    profile_flags=['-I'+str(profile_dir),'-DHB_BUILD_VERSION="'+(ROOT/'runtime/apps/qqmusic/VERSION').read_text().strip()+'"']
if device_app:
    profile_dir=Path(sys.argv[sys.argv.index('--device-app')+1]).resolve()
    assert profile_dir.is_relative_to(ROOT/'work') and (profile_dir/'qqmusic_profile.h').is_file()
    own[2]='runtime/apps/qqmusic/qqmusic_main.c'
    own+=['runtime/apps/qqmusic/qqmusic_installation.c','runtime/apps/qqmusic/qqmusic_workspace.c','runtime/apps/qqmusic/qqmusic_wifi.c','runtime/apps/qqmusic/qqmusic_wifi_link.c','runtime/native/syscalls.S']
    own[own.index('runtime/native/linux_signals_posix.c')]='runtime/native/linux_signals.c'
    profile_flags=['-I'+str(profile_dir),'-DQQ_NATIVE_FULL','-DHB_BUILD_VERSION="'+(ROOT/'runtime/apps/qqmusic/VERSION').read_text().strip()+'"']
    if audio_preview:
        reviewed=json.loads((profile_dir/'profile-report.json').read_text())
        assert reviewed['profile_sha256']==hashlib.sha256((profile_dir/'qqmusic_preview_profile.h').read_bytes()).hexdigest()
        assert reviewed['device_identity_observed_read_only'] and reviewed['mode1_page_verified']
        own+=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('preview_wire','preview_transport','preview_supervisor','preview_source_job','preview_session','preview_service','preview_runtime','preview_receipt','preview_producer','preview_pcm','preview_owners','preview_handoff','preview_device_posix','preview_device','preview_decode_worker','preview_decode','preview_client','preview_binding','entry_preview','program_preview')]
        profile_flags+=['-DQQ_NATIVE_PREVIEW']
flags=['-std=gnu99','-O2','-fwrapv','-fsigned-char','-DQQ_CODEC_PORTABLE_C','-DHAVE_ALLOCA_H','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-ffunction-sections','-fdata-sections',
       '-I'+str(work/'include'),'-I'+str(vendor/'ogg/include'),'-I'+str(vendor/'tremor'),'-I'+str(vendor/'shine/src/lib')]
flags+=['-isystem',str(stb)]
flags+=network_flags
if file_import:flags+=['-DHB_STORE_SONY_LIBC']
objects=[]
header_key=b''.join(p.read_bytes() for p in sorted((ROOT/'runtime/apps/qqmusic').glob('*.h')))+b''.join(p.read_bytes() for p in sorted(vendor.rglob('*.h')))+config.encode()
dependencies=['tools/fixtures/qqmusic_volume.c'] if file_import and not device_app else []
if live_session:dependencies+=['runtime/apps/qqmusic/qqmusic_main.c']
if network_import and not job_import:dependencies+=['tools/fixtures/qqmusic_transfer_import.h']
if binding_import and not device_app:dependencies+=['tools/fixtures/qqmusic_binding.h']
header_key+=b''.join((ROOT/p).read_bytes() for p in dependencies)
if audio_preview:header_key+=(profile_dir/'qqmusic_preview_profile.h').read_bytes()
for i,path in enumerate(third+[ROOT/p for p in own]):
    obj=work/(str(i)+'-'+path.stem+'.o')
    extra=profile_flags if (live_session and path.name=='qqmusic_live_session.c') or (device_app and path.name=='qqmusic_main.c') else []
    cmd=['arm-linux-gnueabi-gcc',*flags,*extra,*(['-Wall','-Wextra','-Werror'] if path.is_relative_to(ROOT/'runtime/apps') or path.is_relative_to(ROOT/'tools/fixtures') else []),'-c',str(path),'-o',str(obj)]
    key=hashlib.sha256(path.read_bytes()+header_key+'\n'.join(cmd[:-2]).encode()).hexdigest();stamp=obj.with_suffix('.key')
    if not obj.exists() or not stamp.exists() or stamp.read_text()!=key:
        subprocess.run(cmd,cwd=ROOT,check=True);stamp.write_text(key)
    objects.append(str(obj))
app=work/(suffix+'.arm')
subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie',*wrap,'-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,*network_libs,str(work/'libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
report={'built':True,'tested':False,'device_tested':False,'objective_complete':False,'artifact_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),
        'libm_sha256':hashlib.sha256((work/'libm.so.6').read_bytes()).hexdigest(),
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in third+[ROOT/p for p in own+dependencies]},
        'source_provenance_sha256':hashlib.sha256((ROOT/'sources/qqmusic-codec-sources.json').read_bytes()).hexdigest(),
        'image_provenance_sha256':hashlib.sha256((ROOT/'sources/qqmusic-image-sources.json').read_bytes()).hexdigest(),
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['Portable C only, no codec inline ARM assembly.','No device performance/heap qualification, user-volume adapter or app integration.']}
if network_import:report['network_dependencies']={str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in network_libs[1:]}
report['audio_preview_enabled']=audio_preview
(work/build_name).write_text(json.dumps(report,indent=2)+'\n');print('ARM codec test ELF built:',app.stat().st_size,'bytes')
if '--host' in sys.argv or '--asan' in sys.argv:
    host_flags=['-std=gnu99','-O2','-fwrapv','-fsigned-char','-DQQ_CODEC_PORTABLE_C','-DHAVE_ALLOCA_H',
                '-I'+str(work/'include'),'-I'+str(vendor/'ogg/include'),'-I'+str(vendor/'tremor'),'-I'+str(vendor/'shine/src/lib')]
    host_flags+=['-isystem',str(stb)]
    sanitizer=['-g','-O1','-fsanitize=address','-fno-omit-frame-pointer'] if '--asan' in sys.argv else []
    host_own=[p for p in own if p.startswith('runtime/apps/') or p.startswith('tools/fixtures/') or p=='runtime/native/sha256.c']
    subprocess.run(['gcc-12',*host_flags,*sanitizer,*wrap,*[str(p) for p in third],*[str(ROOT/p) for p in host_own],'-lm','-o',str(work/(suffix+('.asan' if sanitizer else '.host')))],cwd=ROOT,check=True)
    report['host_artifact_sha256']=hashlib.sha256((work/(suffix+('.asan' if sanitizer else '.host'))).read_bytes()).hexdigest()
    (work/build_name).write_text(json.dumps(report,indent=2)+'\n')

