"""Actual limited PCM decoding of newly generated synthetic Vorbis/QMC, no IO devices."""
from pathlib import Path
import base64,hashlib,importlib.util,json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-decode';w.mkdir(exist_ok=True)
vendor=ROOT/'third_party/qqmusic-codecs';lib=ROOT/'work/arm-signal-tests/lib'
tremor=['mdct','block','window','synthesis','info','floor1','floor0','vorbisfile','res012','mapping0','registry','codebook','sharedbook']
sources=[vendor/'tremor'/(n+'.c') for n in tremor]+[vendor/'ogg/src/framing.c',vendor/'ogg/src/bitwise.c']+[ROOT/p for p in ('runtime/apps/qqmusic/qqmusic_preview_decode.c','runtime/apps/qqmusic/qqmusic_preview_session.c','runtime/apps/qqmusic/qqmusic_preview_pcm.c','runtime/apps/qqmusic/qqmusic_qmc.c','runtime/apps/qqmusic/qqmusic_protocol.c','tools/fixtures/qqmusic_preview_decode.c')]
flags=['-std=gnu99','-fwrapv','-fsigned-char','-DHAVE_ALLOCA_H','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'work/qqmusic-codec/include'),'-I'+str(vendor/'ogg/include'),'-I'+str(vendor/'tremor')]
host=w/'preview.sanitized';arm=w/'preview.arm'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address',*map(str,sources),'-Wl,--gc-sections','-o',str(host)],check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--gc-sections,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*map(str,sources),'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
ref_path=ROOT/'third_party/qmc-reference/qmc2_reference.py';assert hashlib.sha256(ref_path.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_reference',ref_path);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
cases=[]
with tempfile.TemporaryDirectory(dir=w,prefix='synthetic-') as directory:
 p=Path(directory);ogg=p/'source.ogg'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar','44100','-ac','2','-c:a','libvorbis',str(ogg)],check=True)
 inputs=[(ogg,None)]
 for length in (64,512):
  key=bytes((i*37+19)%256 for i in range(length));encoded=p/f'key-{length}';encoded.write_bytes(base64.b64encode(key));data=bytearray(ogg.read_bytes())
  if length>300:ref.RC4(key).decrypt_into(data,0)
  else:ref.map_decrypt(data,key)
  encrypted=p/f'source-{length}.mgg';encrypted.write_bytes(data);inputs.append((encrypted,encoded))
 for rate,channels in ((32000,1),(32000,2),(44100,1),(48000,1),(48000,2)):
  path=p/f'plain-{rate}-{channels}.ogg';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar',str(rate),'-ac',str(channels),'-c:a','libvorbis',str(path)],check=True);inputs.append((path,None))
 for backend,prefix in [('asan',[str(host)]),('arm',['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)])]:
  for source,key in inputs:
   variants=[(250,'ok'),(30000,'ok'),(250,'fragment'),(250,'cancel'),(250,'sinkfail'),(250,'formatfail'),(0,'invalid'),(31000,'invalid')]
   if source.name.startswith('plain-'):variants=[(250,'ok'),(30000,'ok')]
   for ms,mode in variants:
    before=hashlib.sha256(source.read_bytes()).hexdigest();result=subprocess.run(prefix+[str(source),str(key) if key else '-',str(ms),mode],capture_output=True,timeout=30)
    assert b'AddressSanitizer' not in result.stderr and b'runtime error:' not in result.stderr,result.stderr[-2000:]
    assert result.returncode==0,(backend,source.name,ms,mode,result.stderr[-2000:])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    if mode in ('ok','fragment'):assert len(result.stdout)==(11025 if ms==250 else 44100)*4
    else:assert not result.stdout
    cases.append({'backend':backend,'source':source.name,'milliseconds':ms,'mode':mode,'passed':True})
(w/'report.json').write_text(json.dumps({'passed':True,'cases':cases,'actual_pcm_output':True,'session_coordinator_integration':True,'pcm_normalization_integration':True,'stop_restore_release_on_all_paths':True,'physical_device_accessed':False,'account_accessed':False,'limits':['Completed synthetic source supplied by callback; no live download, source lease, PCM device or UI integration.','Test covers decoded duration limit and consumer cancellation; wall-clock playback timing is not measured.']},indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(cases),'device_tested':False}))
