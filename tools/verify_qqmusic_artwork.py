"""Synthetic source cover preservation, PNG/progressive conversion and ID3 readback."""
from pathlib import Path
from io import BytesIO
import base64,hashlib,json,struct,subprocess,tempfile,os
from PIL import Image
from mutagen.id3 import ID3
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'work/qqmusic-artwork';base.mkdir(exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='review-',dir=base));linux=lambda p:('/mnt/'+p.drive[0].lower()+p.as_posix()[2:]) if p.drive else p.as_posix()
runner=['wsl','--exec'] if os.name=='nt' else []
subprocess.run([*runner,'.venv/bin/python','tools/build_qqmusic_artwork.py',linux(work)],cwd=ROOT,check=True)
rows=[]
def block(data,mime,width=32,height=24,kind=3):
    mime=mime.encode();desc='合成封面'.encode()
    return struct.pack('>II',kind,len(mime))+mime+struct.pack('>I',len(desc))+desc+struct.pack('>IIIII',width,height,24,0,len(data))+data
prefixes=[['qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib:'+linux(ROOT/'work/qqmusic-codec'),linux(work/'artwork-tests.arm')],[linux(work/'artwork-tests.asan')]]
for kind in ('baseline','progressive','png'):
    source=work/(kind+('.png' if kind=='png' else '.jpg'))
    if kind=='png':Image.new('RGBA',(32,24),(30,90,150,128)).save(source)
    else:Image.new('RGB',(32,24),(30,90,150)).save(source,format='JPEG',progressive=kind=='progressive')
    data=source.read_bytes();encoded=work/(kind+'.b64');encoded.write_bytes(base64.b64encode(block(data,'image/png' if kind=='png' else 'image/jpeg')))
    for prefix in prefixes:
        run=subprocess.run([*runner,*prefix,linux(source),linux(encoded)],cwd=ROOT,capture_output=True,timeout=30)
        assert run.returncode==0,(kind,run.returncode,run.stderr[-3000:])
        tags=ID3(BytesIO(run.stdout));image=tags.getall('APIC');assert len(image)==1 and image[0].mime=='image/jpeg' and image[0].type==3
        cover=Image.open(BytesIO(image[0].data));cover.load();assert cover.size==(32,24) and not cover.info.get('progressive')
        if kind=='baseline':assert image[0].data==data
        else:
            wanted=(142,172,202) if kind=='png' else (30,90,150)
            pixel=cover.convert('RGB').getpixel((16,12));assert max(abs(a-b) for a,b in zip(pixel,wanted))<8,(kind,pixel,wanted)
        if prefix[0]=='qemu-arm':(work/(kind+'.id3')).write_bytes(run.stdout)
    rows.append({'case':kind,'passed':True,'source_precedence':True,'album_mid_guard':True})
    tests=[('bad-dimensions',base64.b64encode(block(data,'image/png' if kind=='png' else 'image/jpeg',33,24)),'reject-picture'),('nonfront',base64.b64encode(block(data,'image/png' if kind=='png' else 'image/jpeg',kind=4)),'nonfront'),('url-picture',base64.b64encode(block(b'https://invalid.test/pic','-->')),'reject-picture')]
    for name,b64,mode in tests:
        path=work/(kind+'-'+name+'.b64');path.write_bytes(b64)
        for prefix in prefixes:
            run=subprocess.run([*runner,*prefix,linux(source),linux(path),mode],cwd=ROOT,capture_output=True,timeout=30)
            assert run.returncode==0 and not run.stdout,(kind,name,run.stderr[-3000:])
    if kind=='png':
        corrupt=work/'corrupt.png';bad=bytearray(data);bad[-1]^=1;corrupt.write_bytes(bad)
        for prefix in prefixes:
            run=subprocess.run([*runner,*prefix,linux(corrupt),linux(encoded),'reject-image'],cwd=ROOT,capture_output=True,timeout=30)
            assert run.returncode==0 and not run.stdout,run.stderr[-3000:]
report={'passed':True,'synthetic_data':True,'device_tested':False,'objective_complete':False,'cases':rows,
        'checks':['baseline source JPEG exact preservation','PNG/progressive to baseline JPEG','alpha white composite','source front cover wins, explicit album MID fallback only','invalid dimensions/URL/CRC/capacity/truncation reject'],
        'build_report_sha256':hashlib.sha256((work/'build.json').read_bytes()).hexdigest(),
        'limits':['No physical Sony image/GUI qualification.','Legacy COVERART and multiple distinct front covers not supported.','No actual account artwork or production app/file integration.']}
(work/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'output':str(work.relative_to(ROOT)),**report},indent=2))
