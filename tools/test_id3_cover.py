"""Bounded PIC/APIC extraction, including optional read-only real-track input."""
import argparse,hashlib,io,json,os,subprocess,time
from pathlib import Path
from PIL import Image
from app_registry import ROOT
from player_arm_guest import stock_libraries
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);args=p.parse_args()
out=ROOT/'work/id3-cover-tests'/str(time.time_ns());out.mkdir(parents=True)
sources=['runtime/platform/player/id3_cover.c','runtime/native/sha256.c','tools/fixtures/id3_cover.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0']
host=out/'extract.host';subprocess.run(['gcc-12',*flags,'-fsanitize=address,undefined',*sources,'-o',str(host)],cwd=ROOT,check=True)
libs=stock_libraries();arm=out/'extract.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
def syn(n):return bytes((n>>21&127,n>>14&127,n>>7&127,n&127))
def frame(version,name,payload,flags=0):return name.encode()+((len(payload).to_bytes(3,'big')) if version==2 else (syn(len(payload)) if version==4 else len(payload).to_bytes(4,'big'))+bytes((0,flags)))+payload
def tag(version,frames,flags=0):return b'ID3'+bytes((version,0,flags))+syn(len(frames))+frames+b'\xff\xfb'+bytes(32)
images={}
for fmt in ('JPEG','PNG'):
 b=io.BytesIO();Image.new('RGB',(8,8),(32,100,200)).save(b,fmt);images[fmt]=b.getvalue()
rows=[];cases=[]
for version in (2,3,4):
 for encoding,description in ((0,b'Front\0'),(1,b'\xff\xfeF\0r\0o\0n\0t\0\0\0'),(2,b'\0F\0r\0o\0n\0t\0\0'),(3,'封面'.encode()+b'\0')):
  for fmt in ('JPEG','PNG'):
   mime=(b'JPG' if fmt=='JPEG' else b'PNG') if version==2 else (b'image/jpeg\0' if fmt=='JPEG' else b'image/png\0')
   payload=bytes((encoding,))+mime+b'\x03'+description+images[fmt]
   cases.append((f'v{version}-e{encoding}-{fmt}',tag(version,frame(version,'PIC' if version==2 else 'APIC',payload)),0,images[fmt]))
base=b'\0image/jpeg\0\x03\0'+images['JPEG']
cases.extend([('no-art',tag(3,b''),-2,None),('url',tag(3,frame(3,'APIC',b'\0-->\0\x03\0https://example.invalid/image')),-2,None),('truncated',tag(3,frame(3,'APIC',base))[:16],-8,None),('tag-unsync',tag(3,frame(3,'APIC',base),128),-3,None),('oversize',tag(3,frame(3,'APIC',base+bytes(131072))),-3,None)])
for name,data,result,image in cases:
 path=out/(name+'.mp3');path.write_bytes(data);before=hashlib.sha256(data).hexdigest()
 commands=[[str(host),str(path)],['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm),str(path)]]
 for command in commands:
  run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=20,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'))
  assert run.returncode==0,(name,run.stdout,run.stderr)
  assert run.stdout.startswith(f'RESULT {result} BYTES '),(name,run.stdout)
  if image:assert f'BYTES {len(image)} SHA256 {hashlib.sha256(image).hexdigest()}' in run.stdout,(name,run.stdout)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before;rows.append(name)
if args.source:
 from mutagen.id3 import ID3
 before=hashlib.sha256(args.source.read_bytes()).hexdigest();pictures=ID3(args.source).getall('APIC');front=next(a for a in pictures if int(a.type)==3)
 for command in ([str(host),str(args.source)],['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(arm),str(args.source)]):
  run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=20)
  assert run.returncode==0 and f'RESULT 0 BYTES {len(front.data)} SHA256 {hashlib.sha256(front.data).hexdigest()}' in run.stdout,run.stdout+run.stderr
 assert hashlib.sha256(args.source.read_bytes()).hexdigest()==before
report=dict(passed=True,cases=rows,host_sanitizers=True,original_libc_arm926=True,real_track_checked=bool(args.source),source_file_unchanged=True,device_accessed=False,
 source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources+['runtime/platform/player/id3_cover.h','tools/test_id3_cover.py']},limits=['A parser check is not integration with Sony cover lookup, JPEG display, remote transport or sleep qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
