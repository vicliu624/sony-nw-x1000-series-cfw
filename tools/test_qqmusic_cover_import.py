"""Targeted synthetic lazy-cover conversion, real ARM codec and ASan backend."""
from pathlib import Path
import base64,hashlib,json,os,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];codec=ROOT/'work/qqmusic-codec';base=ROOT/'work/qqmusic-cover-import';base.mkdir(exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='synthetic-',dir=base));lib=ROOT/'work/arm-signal-tests/lib'
built=json.loads((codec/'build.json').read_text());assert hashlib.sha256((codec/'codec-tests.arm').read_bytes()).hexdigest()==built['artifact_sha256']
assert hashlib.sha256((codec/'codec-tests.asan').read_bytes()).hexdigest()==built['host_artifact_sha256']
def ffmpeg(*args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n',*map(str,args)],check=True,capture_output=True)
source=work/'no-cover.ogg';ffmpeg('-f','lavfi','-i','sine=frequency=440:duration=0.5','-ac','2','-ar','44100','-c:a','libvorbis','-metadata','title=Source title',source)
for color in ('red','blue'):ffmpeg('-f','lavfi','-i',f'color=c={color}:s=64x64','-frames:v','1','-c:v','mjpeg','-threads','1',work/f'{color}.jpg')
blue=(work/'blue.jpg').read_bytes();red=(work/'red.jpg').read_bytes();with_cover=work/'source-cover.ogg'
picture=struct.pack('>II',3,10)+b'image/jpeg'+struct.pack('>IIIIII',0,64,64,24,0,len(blue))+blue
ffmpeg('-i',source,'-c:a','copy','-metadata','METADATA_BLOCK_PICTURE='+base64.b64encode(picture).decode(),with_cover)
invalid=work/'invalid.jpg';invalid.write_bytes(b'not-an-image')
prefixes={'arm':['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(codec),str(codec/'codec-tests.arm')], 'asan':[str(codec/'codec-tests.asan')]}
rows=[]
for backend,prefix in prefixes.items():
 for mode,input_path,cover,expected in [('import-cover',source,work/'red.jpg',red),('import-cover-skip',with_cover,work/'does-not-exist.jpg',blue),('import-cover-fail',source,work/'red.jpg',None),('import-cover-invalid',source,invalid,None)]:
  original=hashlib.sha256(input_path.read_bytes()).hexdigest();env=os.environ.copy();env['QQ_SYNTHETIC_COVER']=str(cover)
  result=subprocess.run(prefix+[str(input_path),'192',mode],env=env,capture_output=True,check=True,timeout=30)
  assert hashlib.sha256(input_path.read_bytes()).hexdigest()==original
  if expected is None:assert not result.stdout
  else:
   output=work/f'{backend}-{mode}.mp3';output.write_bytes(result.stdout);assert result.stdout[:5]==b'ID3\x03\0'
   probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],check=True,capture_output=True).stdout)
   assert probe['format']['tags']['title']=='Source title'
   pictures=[stream for stream in probe['streams'] if stream['codec_type']=='video'];assert len(pictures)==1 and pictures[0]['codec_name']=='mjpeg' and pictures[0]['disposition']['attached_pic']==1
   extracted=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-map','0:v:0','-c:v','copy','-f','image2pipe','-'],check=True,capture_output=True).stdout;assert extracted==expected
   subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(output),'-f','null','-'],check=True,capture_output=True)
  rows.append({'backend':backend,'case':mode,'passed':True})
report={'passed':True,'synthetic_only':True,'account_accessed':False,'device_accessed':False,'network_tested':False,'checks':rows,'limits':['Exercises the lazy callback and real conversion, not the production HTTPS cover fetch.','No physical volume, QQ login or fresh account MGG tested.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');(base/'latest.json').write_text(json.dumps({'report':str((work/'report.json').relative_to(ROOT))})+'\n');print(json.dumps(report,indent=2))
