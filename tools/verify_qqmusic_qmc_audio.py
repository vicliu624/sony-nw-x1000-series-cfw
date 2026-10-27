"""Windows PC-only synthetic OGG encrypt/decrypt/decode check, never a real account."""
from pathlib import Path
import base64,hashlib,importlib.util,json,struct,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
ref_path=ROOT/'third_party/qmc-reference/qmc2_reference.py'
assert hashlib.sha256(ref_path.read_bytes()).hexdigest()=='d539d33d11bc16ee0904877a21bbf7a87256418fc405065f482bbb248c36763b'
spec=importlib.util.spec_from_file_location('qmc_reference',ref_path);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
base=ROOT/'work/qqmusic-qmc-audio';base.mkdir(exist_ok=True)
work=Path(tempfile.mkdtemp(prefix='review-',dir=base))
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=660:duration=1','-c:a','libvorbis','-q:a','4',str(work/'source.ogg')],check=True)
plain=(work/'source.ogg').read_bytes();assert plain[:4]==b'OggS' and len(plain)<65536
raw=bytes((i*37+19)%256 for i in range(512));encoded=base64.b64encode(raw)
assert ref.derive_key(encoded)==raw
encrypted=bytearray(plain);ref.RC4(raw).decrypt_into(encrypted,0)
fixture=struct.pack('<I',1)+struct.pack('<IIIIQ',1,len(encoded),len(raw),len(plain),0)+encoded+raw+encrypted+plain
(work/'synthetic.bin').write_bytes(fixture)
subprocess.run(['wsl','--exec','.venv/bin/python','tools/test_qqmusic_qmc.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
linux='/mnt/'+work.drive[0].lower()+work.as_posix()[2:]
recovered=subprocess.check_output(['wsl','--exec','qemu-arm','-cpu','arm926','work/arm-signal-tests/lib/ld-linux.so.3','--library-path','work/arm-signal-tests/lib','work/qqmusic-qmc/qmc-tests.arm',linux+'/synthetic.bin','--emit'],cwd=ROOT)
assert recovered==plain
(work/'recovered.ogg').write_bytes(recovered)
subprocess.run(['ffmpeg','-v','error','-i',str(work/'recovered.ogg'),'-f','null','-'],check=True)
subprocess.run(['ffmpeg','-v','error','-i',str(work/'recovered.ogg'),'-c:a','libmp3lame','-b:a','192k',str(work/'pc-conversion.mp3')],check=True)
subprocess.run(['ffmpeg','-v','error','-i',str(work/'pc-conversion.mp3'),'-f','null','-'],check=True)
report={'passed':True,'synthetic_audio':True,'real_account_tested':False,'device_tested':False,'objective_complete':False,
        'checks':['Python reference synthetic RC4 encryption -> ARM C key derivation and decryption','OGG byte-for-byte recovery','PC FFmpeg full OGG decode','PC-only OGG->MP3 and full decode'],
        'output':str((work/'pc-conversion.mp3').relative_to(ROOT)),
        'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'source.ogg',work/'recovered.ogg',work/'pc-conversion.mp3')},
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits':['Synthetic one-second file, no musicex footer or real QQ resource.','MP3 encoder runs on development PC only, not implemented/deployed on player.','No metadata merge, stock import or user-volume transaction integration.']}
(work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
