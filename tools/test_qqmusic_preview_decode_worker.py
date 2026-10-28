"""Real Vorbis/QMC decode -> normalize -> actual pipe worker on host/stock ARM."""
from pathlib import Path
import base64,hashlib,importlib.util,json,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-decode-worker';w.mkdir(exist_ok=True)
vendor=ROOT/'third_party/qqmusic-codecs';lib=ROOT/'work/arm-signal-tests/lib'
tremor=['mdct','block','window','synthesis','info','floor1','floor0','vorbisfile','res012','mapping0','registry','codebook','sharedbook']
native=['runtime/apps/qqmusic/'+n+'.c' for n in ['qqmusic_preview_decode','qqmusic_preview_pcm','qqmusic_preview_transport','qqmusic_preview_decode_worker','qqmusic_preview_wire','qqmusic_qmc','qqmusic_protocol']]+['runtime/native/linux_process_posix.c','runtime/store/deadline.c','tools/fixtures/qqmusic_preview_decode_worker.c']
sources=[vendor/'tremor'/(n+'.c') for n in tremor]+[vendor/'ogg/src/framing.c',vendor/'ogg/src/bitwise.c']+[ROOT/p for p in native]
flags=['-std=gnu99','-fwrapv','-fsigned-char','-DHAVE_ALLOCA_H','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'work/qqmusic-codec/include'),'-I'+str(vendor/'ogg/include'),'-I'+str(vendor/'tremor')]
host=w/'worker.sanitized';arm=w/'worker.arm'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address',*map(str,sources),'-Wl,--gc-sections','-o',str(host)],check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--gc-sections,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*map(str,sources),'runtime/native/syscalls.S','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
reference=ROOT/'third_party/qmc-reference/qmc2_reference.py';assert hashlib.sha256(reference.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('reference',reference);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
cases=[]
with tempfile.TemporaryDirectory(dir=w) as directory:
 p=Path(directory);inputs=[]
 for rate,ch in [(44100,2),(32000,1),(48000,2)]:
  source=p/f'{rate}-{ch}.ogg';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar',str(rate),'-ac',str(ch),'-c:a','libvorbis',str(source)],check=True);inputs.append((source,None))
 for length in [64,512]:
  key=bytes((i*37+19)%256 for i in range(length));encoded=p/f'key-{length}';encoded.write_bytes(base64.b64encode(key));data=bytearray(inputs[0][0].read_bytes())
  if length>300:ref.RC4(key).decrypt_into(data,0)
  else:ref.map_decrypt(data,key)
  source=p/f'{length}.mgg';source.write_bytes(data);inputs.append((source,encoded))
 for backend,prefix in [('asan',[str(host)]),('arm',['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)])]:
  outputs={}
  for source,key in inputs:
   before=hashlib.sha256(source.read_bytes()).hexdigest();r=subprocess.run(prefix+[str(source),str(key) if key else '-', '250'],capture_output=True,timeout=20)
   assert r.returncode==0 and b'AddressSanitizer' not in r.stderr,(backend,r.stderr[-1800:]);assert len(r.stdout)==11025*4;assert hashlib.sha256(source.read_bytes()).hexdigest()==before
   if key:assert r.stdout==outputs['44100-2.ogg']
   outputs[source.name]=r.stdout;cases.append({'backend':backend,'source':source.name,'frames':11025})
report={'passed':True,'host_asan':True,'stock_arm_libc':True,'cases':cases,'real_pipe_transport':True,'physical_device_accessed':False,'account_accessed':False,'limits':['Synthetic complete source only, no download or live authorization.','Actual decoder, resampler and pipe sender execute; no audio output or UI binding.'],'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in native}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(cases),'device_accessed':False}))
