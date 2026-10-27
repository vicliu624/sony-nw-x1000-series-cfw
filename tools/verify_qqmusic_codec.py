"""Windows PC fixture generation, actual ARM Vorbis->MP3, independent decode."""
from pathlib import Path
import array,base64,hashlib,importlib.util,json,struct,subprocess,tempfile,time
from io import BytesIO
from mutagen.id3 import ID3
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'work/qqmusic-codec-audio';base.mkdir(exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='review-',dir=base))
subprocess.run(['wsl','--exec','.venv/bin/python','tools/build_qqmusic_codec.py','--asan'],cwd=ROOT,check=True)
linux=lambda p:'/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
rows=[]
def frame_count(data,rate,channels):
    pos=0;count=0;bitrates=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]
    while pos<len(data):
        assert pos+4<=len(data)
        h=int.from_bytes(data[pos:pos+4],'big');assert h>>21==0x7ff and (h>>19)&3==3 and (h>>17)&3==1
        bitrate=bitrates[(h>>12)&15];sr=[44100,48000,32000,0][(h>>10)&3]
        assert bitrate==192 and sr==rate and (1 if (h>>6)&3==3 else 2)==channels
        length=144000*bitrate//sr+((h>>9)&1);assert pos+length<=len(data)
        pos+=length;count+=1
    assert pos==len(data);return count
for rate,channels in [(44100,1),(44100,2),(48000,1),(32000,2)]:
    stem=f'{rate}-{channels}';source=work/(stem+'.ogg');output=work/(stem+'.mp3')
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar',str(rate),'-ac',str(channels),'-c:a','libvorbis','-q:a','4',str(source)],check=True)
    start=time.perf_counter()
    run=subprocess.run(['wsl','--exec','qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib:work/qqmusic-codec','work/qqmusic-codec/codec-tests.arm',linux(source),'192'],cwd=ROOT,capture_output=True,timeout=60)
    assert run.returncode==0,(stem,run.returncode,run.stderr[-3000:])
    assert run.stdout
    frames=frame_count(run.stdout,rate,channels)
    with output.open('xb') as f:f.write(run.stdout)
    elapsed=time.perf_counter()-start
    probed=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],check=True,capture_output=True)
    assert not probed.stderr;probe=json.loads(probed.stdout)
    audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert audio['codec_name']=='mp3' and int(audio['sample_rate'])==rate and audio['channels']==channels
    duration=float(probe['format']['duration']);assert .9<duration<1.15,(stem,duration)
    decode=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','-'],check=True,capture_output=True)
    assert not decode.stderr;decoded=decode.stdout
    samples=array.array('h');samples.frombytes(decoded)
    rms=(sum(v*v for v in samples)/len(samples))**.5
    assert rms>100,(stem,rms)
    host=subprocess.run(['wsl','--exec','work/qqmusic-codec/codec-tests.asan',linux(source),'192'],cwd=ROOT,capture_output=True,timeout=60)
    assert host.returncode==0,(stem,host.stderr[-3000:]);frame_count(host.stdout,rate,channels)
    rows.append({'sample_rate':rate,'channels':channels,'bitrate_kbps':192,'frames':frames,'duration':duration,'decoded_rms':rms,'qemu_wall_seconds':elapsed,'mp3_bytes':len(run.stdout),'sha256':hashlib.sha256(run.stdout).hexdigest()})
negative=[]
bad=work/'invalid.ogg';bad.write_bytes(b'not Ogg Vorbis')
truncated=work/'truncated.ogg';truncated.write_bytes((work/'44100-1.ogg').read_bytes()[:-200])
for name,path,bitrate in [('invalid',bad,192),('truncated',truncated,192),('cancel',work/'44100-1.ogg',192),('read-fail',work/'44100-1.ogg',192),('write-fail',work/'44100-1.ogg',192),('bitrate',work/'44100-1.ogg',999)]:
    for prefix in [['qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib:work/qqmusic-codec','work/qqmusic-codec/codec-tests.arm'],['work/qqmusic-codec/codec-tests.asan']]:
        tested=subprocess.run(['wsl','--exec',*prefix,linux(path),str(bitrate),name],cwd=ROOT,capture_output=True,timeout=60)
        assert tested.returncode==0,(name,tested.returncode,tested.stderr[-3000:])
    negative.append(name)
ref_path=ROOT/'third_party/qmc-reference/qmc2_reference.py'
assert hashlib.sha256(ref_path.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_ref',ref_path);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
qmc=[];plain=(work/'44100-2.ogg').read_bytes();expected_mp3=(work/'44100-2.mp3').read_bytes()
for length in (64,512):
    key=bytes((i*37+19)%256 for i in range(length));encoded=base64.b64encode(key)
    assert ref.derive_key(encoded)==key
    encrypted=bytearray(plain)
    if length>300:ref.RC4(key).decrypt_into(encrypted,0)
    else:ref.map_decrypt(encrypted,key)
    for footer in (False,True):
        name=f'qmc-{length}-{int(footer)}';source=work/(name+'.mgg');keyfile=work/(name+'.key')
        download=bytes(encrypted)+(b'\0'*16+struct.pack('<I',32)+b'\0'*4+b'musicex\0' if footer else b'')
        source.write_bytes(download);keyfile.write_bytes(encoded)
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        for prefix in [['qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib:work/qqmusic-codec','work/qqmusic-codec/codec-tests.arm'],['work/qqmusic-codec/codec-tests.asan']]:
            tested=subprocess.run(['wsl','--exec',*prefix,linux(source),'192','qmc',linux(keyfile)],cwd=ROOT,capture_output=True,timeout=60)
            assert tested.returncode==0,(name,tested.returncode,tested.stderr[-3000:])
            frame_count(tested.stdout,44100,2)
            if prefix[0]=='qemu-arm':assert tested.stdout==expected_mp3,name
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        qmc.append({'key_length':length,'musicex_footer':footer,'source_unchanged':True,'matches_plain_arm_conversion':True})
qmc_negative=[];source=work/'qmc-512-1.mgg';good_key=work/'qmc-512-1.key';wrong_key=work/'wrong.key'
wrong_key.write_bytes(base64.b64encode(bytes([42])*512))
broken=work/'bad-footer.mgg';corrupt=bytearray(source.read_bytes());corrupt[-16:-12]=struct.pack('<I',len(corrupt));broken.write_bytes(corrupt)
prefixes=[['qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib:work/qqmusic-codec','work/qqmusic-codec/codec-tests.arm'],['work/qqmusic-codec/codec-tests.asan']]
for name,path,keyfile in [('wrong-key',source,wrong_key),('invalid-footer',broken,good_key)]:
    for prefix in prefixes:
        tested=subprocess.run(['wsl','--exec',*prefix,linux(path),'192','qmc',linux(keyfile),name],cwd=ROOT,capture_output=True,timeout=60)
        assert tested.returncode==0 and not tested.stdout,(name,tested.returncode,tested.stderr[-3000:])
    qmc_negative.append(name)
for prefix in prefixes:
    fragmented=subprocess.run(['wsl','--exec',*prefix,linux(source),'192','qmc',linux(good_key),'fragments'],cwd=ROOT,capture_output=True,timeout=60)
    assert fragmented.returncode==0,fragmented.stderr[-3000:]
    if prefix[0]=='qemu-arm':assert fragmented.stdout==expected_mp3
metadata_source=work/'metadata-source.ogg'
metadata_args=[]
cover_data=BytesIO();Image.new('RGBA',(32,24),(30,90,150,128)).save(cover_data,format='PNG');cover_data=cover_data.getvalue()
picture=struct.pack('>II',3,9)+b'image/png'+struct.pack('>I',0)+struct.pack('>IIIII',32,24,32,0,len(cover_data))+cover_data
for key,value in {'title':'源标题','artist':'源艺人','album':'源专辑','track':'3','TRACKTOTAL':'12','disc':'1','DISCTOTAL':'2','date':'2025-03-04','genre':'Jazz','composer':'作曲甲','CUSTOM':'保留字段','METADATA_BLOCK_PICTURE':base64.b64encode(picture).decode()}.items():metadata_args+=['-metadata',key+'='+value]
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=1','-ar','44100','-ac','2','-c:a','libvorbis','-q:a','4',*metadata_args,str(metadata_source)],check=True)
original_metadata_hash=hashlib.sha256(metadata_source.read_bytes()).hexdigest();tagged_arm=None
for prefix in prefixes:
    tagged=subprocess.run(['wsl','--exec',*prefix,linux(metadata_source),'192','metadata'],cwd=ROOT,capture_output=True,timeout=60)
    assert tagged.returncode==0,tagged.stderr[-3000:]
    tags=ID3(BytesIO(tagged.stdout));assert tags.version==(2,3,0)
    expected_tags={'TIT2':'源标题','TPE1':'源艺人','TALB':'源专辑','TPE2':'接口专辑艺人','TRCK':'3/12','TPOS':'1/2','TCON':'Jazz','TCOM':'作曲甲','TXXX:CUSTOM':'保留字段','TXXX:DATE':'2025-03-04'}
    for field,value in expected_tags.items():assert str(tags[field])==value,(field,str(tags[field]))
    covers=tags.getall('APIC');assert len(covers)==1 and covers[0].mime=='image/jpeg';decoded_cover=Image.open(BytesIO(covers[0].data));decoded_cover.load();assert decoded_cover.size==(32,24)
    size=10+sum((tagged.stdout[6+i]&127)<<(7*(3-i)) for i in range(4));frame_count(tagged.stdout[size:],44100,2)
    raw_conversion=subprocess.run(['wsl','--exec',*prefix,linux(metadata_source),'192'],cwd=ROOT,capture_output=True,timeout=60)
    assert raw_conversion.returncode==0 and raw_conversion.stdout==tagged.stdout[size:]
    if prefix[0]=='qemu-arm':tagged_arm=tagged.stdout
assert hashlib.sha256(metadata_source.read_bytes()).hexdigest()==original_metadata_hash
metadata_output=work/'metadata-tagged.mp3';metadata_output.write_bytes(tagged_arm)
decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(metadata_output),'-f','null','-'],capture_output=True,check=True);assert not decoded.stderr
raw=bytes((i*37+19)%256 for i in range(512));encrypted=bytearray(metadata_source.read_bytes());ref.RC4(raw).decrypt_into(encrypted,0)
metadata_encrypted=work/'metadata-source.mgg';metadata_encrypted.write_bytes(encrypted+b'\0'*16+struct.pack('<I',32)+b'\0'*4+b'musicex\0')
metadata_key=work/'metadata-source.key';metadata_key.write_bytes(base64.b64encode(raw))
qmc_tagged=subprocess.run(['wsl','--exec',*prefixes[0],linux(metadata_encrypted),'192','qmc',linux(metadata_key),'metadata'],cwd=ROOT,capture_output=True,timeout=60)
assert qmc_tagged.returncode==0 and qmc_tagged.stdout==tagged_arm,qmc_tagged.stderr[-3000:]
metadata_checks={'source_precedence':True,'identity_matched_missing_album_artist_fill':True,'full_date_and_unknown_TXXX':True,'source_picture_to_jpeg_apic':True,'track_disc_totals':True,'source_unchanged':True,'metadata_does_not_change_mp3_frames':True,'qmc_to_tagged_mp3_matches_plain':True}
report={'passed':True,'synthetic_audio':True,'real_account_tested':False,'device_tested':False,'objective_complete':False,'cases':rows,'negative_cases':negative,'qmc_to_codec_cases':qmc,'qmc_negative_cases':qmc_negative,'seven_byte_source_reads':True,'host_asan':True,'metadata_checks':metadata_checks,
        'build_report_sha256':hashlib.sha256((ROOT/'work/qqmusic-codec/build.json').read_bytes()).hexdigest(),
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['ARM library conversion under QEMU, not X1060 throughput/heap/power qualification.','No resampler/multichannel/chained stream support yet.','Synthetic embedded source artwork/metadata only; no real account download, protected sink or full app integration.']}
(work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'output':str(work.relative_to(ROOT)),**report},indent=2))
