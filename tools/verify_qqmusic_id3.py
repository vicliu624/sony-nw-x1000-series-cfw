"""Windows PC-only independent Mutagen/FFmpeg check; all generated data in work/."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
from PIL import Image
from mutagen.id3 import ID3
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'work/qqmusic-id3';base.mkdir(exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='review-',dir=base))
Image.new('RGB',(32,32),(34,67,120)).save(work/'cover.jpg',format='JPEG')
linux='/mnt/'+work.drive[0].lower()+work.as_posix()[2:]
subprocess.run(['wsl','--exec','.venv/bin/python','tools/build_qqmusic_id3_fixture.py',linux],cwd=ROOT,check=True)
subprocess.run(['wsl','--exec','.venv/bin/python','tools/check_stock_id3_frames.py','--tag',linux+'/generated.id3'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
tags=ID3(work/'generated.id3');assert tags.version==(2,3,0)
expected={'TIT2':'测试歌曲 🎵','TPE1':'测试歌手','TALB':'测试专辑','TPE2':'Album Artist','TRCK':'3/12','TPOS':'1/2'}
for key,value in expected.items():assert str(tags[key])==value,(key,str(tags[key]))
assert str(tags['TDRC'])=='2026' # Mutagen normalizes TYER on read.
cover=tags.getall('APIC');assert len(cover)==1 and cover[0].mime=='image/jpeg' and cover[0].type==3
assert cover[0].data==(work/'cover.jpg').read_bytes()
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1','-c:a','libmp3lame','-b:a','128k','-write_xing','0','-id3v2_version','0','-write_id3v1','0',str(work/'source.mp3')],check=True)
audio=(work/'source.mp3').read_bytes();tag=(work/'generated.id3').read_bytes()
with (work/'tagged.mp3').open('xb') as out:out.write(tag);out.write(audio)
assert (work/'tagged.mp3').read_bytes()[len(tag):]==audio
subprocess.run(['ffmpeg','-v','error','-i',str(work/'tagged.mp3'),'-map','0:a:0','-f','null','-'],check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(work/'tagged.mp3')]))
assert any(s['codec_name']=='mp3' for s in probe['streams'])
report={'passed':True,'synthetic_audio':True,'device_tested':False,'ready_to_flash':False,
        'checks':['ARM and host sanitized writer output identical','Mutagen v2.3 Unicode/text/track/disc/year and APIC readback','original stock frame retrieval with missing/truncated/short-buffer cases','MP3 audio payload unchanged','FFmpeg complete synthetic track decode'],
        'output':str((work/'tagged.mp3').relative_to(ROOT)),
        'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'source.mp3',work/'generated.id3',work/'tagged.mp3')},
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['No QQ download or transcoding pipeline.','Stock frame bytes only: no GUI text/JPEG decoding or library refresh qualification.','Writer emits new tag; source metadata preservation/merge still required.']}
(work/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
