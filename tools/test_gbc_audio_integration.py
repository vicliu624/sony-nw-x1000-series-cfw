"""Run the unchanged GBC ELF with synthetic ROM + virtual OSS/FAT/devices."""
from pathlib import Path
import subprocess,shutil,re,json,hashlib,struct,wave
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/gbc-audio-integration';w.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib';prefix=w/'sysroot';(prefix/'lib').mkdir(parents=True,exist_ok=True)
for n in ['libc.so.6','ld-linux.so.3']:shutil.copyfile(lib/n,prefix/'lib'/n)
dl=ROOT/'work/home-key-child-test/sysroot/lib/libdl.so.2';shutil.copyfile(dl,prefix/'lib/libdl.so.2')
for n in ['contents/HOMEBREW/apps/gbc','contents/HOMEBREW/data/gbc/roms','contents/HOMEBREW/data/gbc/saves','proc']:(prefix/n).mkdir(parents=True,exist_ok=True)
(prefix/'proc/100/fd').mkdir(parents=True,exist_ok=True)
for name,target in [('proc/100/fd/3','/dev/sound/dsp'),('proc/100/exe','/usr/local/bin/SpiderApp')]:
 p=prefix/name
 if not p.is_symlink():p.symlink_to(target)
(prefix/'proc/mounts').write_text('/dev/mtdblock/2 /contents vfat rw 0 0\n')
s=(ROOT/'tools/test_emulator_cores.c').read_text();body=re.search(r'unsigned char code\[\] = \{(.*?)\};',s,re.S).group(1);code=bytes(int(x.strip(),0)for x in body.split(',')if x.strip());rom=bytearray(32768);rom[0x100:0x103]=b'\xc3\x50\x01';rom[0x134:0x140]=b'HB SYNTHETIC';rom[0x143]=0x80;rom[0x147]=3;rom[0x149]=2;rom[0x150:0x150+len(code)]=code;rom[0x14d]=(-sum(rom[0x134:0x14d])-25)&255
(prefix/'contents/HOMEBREW/data/gbc/roms/synthetic.gbc').write_bytes(rom)
flags=['-std=c99','-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-fno-builtin','-fno-stack-protector','-shared','-nostdlib','-Wl,--hash-style=sysv','-Wl,--build-id=none']
built=subprocess.run(['arm-linux-gnueabi-gcc',*flags,'tools/fixtures/gbc_pcm_preload.c','runtime/native/syscalls.S',str(lib/'libc.so.6'),str(dl),'-lgcc','-o',str(w/'pcm.so')],cwd=ROOT,capture_output=True,text=True);assert built.returncode==0,built.stderr
# Extend the virtual touch script: choose ROM, pause, mute, enable, resume,
# pause, adjust volume, and exit. Production app code is unchanged.
device=(ROOT/'tools/fixtures/device_preload.c').read_text().replace('../../runtime/native/font.inc',str(ROOT/'runtime/native/font.inc'))
device=device.replace('static int max_events(void){','static int max_events(void){if(getenv("EMU_AUDIO_MENU_TEST"))return 16;')
device=device.replace('event==8||getenv("HB_TEST_STOP")','event==8||event==16||getenv("HB_TEST_STOP")')
device=device.replace('assert(touch&&timeout==50&&event<max_events())','assert(touch&&timeout==0&&event<max_events())')
device=device.replace('unsigned rx=(x*2929+239)/240', 'if(getenv("EMU_AUDIO_MENU_TEST")){static const unsigned xy[8][2]={{80,60},{210,12},{80,230},{80,230},{80,70},{210,12},{200,336},{120,410}};x=xy[event/2][0];y=xy[event/2][1];}unsigned rx=(x*2929+239)/240')
(w/'devices-menu.c').write_text(device)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,str(w/'devices-menu.c'),'runtime/native/syscalls.S',str(lib/'libc.so.6'),'-lgcc','-o',str(w/'devices-menu.so')],cwd=ROOT,check=True)
app=ROOT/'work/emulator-apps/gbc/package/app';capture=w/'output.s16le';frame=w/'frame.rgb565'
command=['qemu-arm','-cpu','arm926','-L',str(prefix)]
for v in ['LD_PRELOAD='+str(w/'pcm.so')+':'+str(w/'devices-menu.so'),'HB_TEST_PREFIX='+str(prefix),'EMU_AUDIO_MENU_TEST=1','HB_TEST_MODE=loop','HB_TEST_TARGET=store','PCM_CAPTURE='+str(capture),'HB_TEST_FRAME='+str(frame)]:command+=['-E',v]
r=subprocess.run(command+[str(app)],cwd=ROOT,capture_output=True,text=True,timeout=25);(w/'run.log').write_text(r.stderr);assert r.returncode==0,(r.returncode,r.stderr)
assert r.stderr.count('PCM MIXER RESTORED')==2 and r.stderr.count('PCM AUDIO CAPTURED')==2,r.stderr
for marker in ['PCM AUDIO CAPTURED','PCM MIXER RESTORED','VDEV RELEASE COMPLETE']:assert marker in r.stderr,r.stderr
raw=capture.read_bytes();assert len(raw)>100 and len(raw)%4==0;values=struct.unpack('<'+'h'*(len(raw)//2),raw);assert max(values)-min(values)>100
with wave.open(str(w/'output.wav'),'wb')as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(22050);f.writeframes(raw)
report={'passed':True,'production_app_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'exit':r.returncode,'pcm_bytes':len(raw),'pcm_format':'22050 Hz S16LE stereo','sample_range':[min(values),max(values)],'events':r.stderr.splitlines(),'source_sha256':hashlib.sha256((ROOT/'tools/fixtures/gbc_pcm_preload.c').read_bytes()).hexdigest(),'scope':'Actual production ARM ELF/stock libc loads synthetic ROM, generates APU sound, converts and writes through production POSIX/queue, resets/closes and restores mixer, releases graphics. OSS/codec and FAT metadata are virtual; no physical headphone qualification.','hardware_tested':False}
# Verify that the production error screen reports the original DSP errno,
# even though cleanup closes the mixer afterwards.
busy_frame=w/'busy-frame.rgb565';cmd=['qemu-arm','-cpu','arm926','-L',str(prefix)]
for v in ['LD_PRELOAD='+str(w/'pcm.so')+':'+str(w/'devices-menu.so'),'HB_TEST_PREFIX='+str(prefix),'HB_TEST_MODE=loop','HB_TEST_TARGET=store','PCM_BUSY=1','PCM_CAPTURE='+str(w/'unused.raw'),'HB_TEST_FRAME='+str(busy_frame)]:cmd+=['-E',v]
busy=subprocess.run(cmd+[str(app)],cwd=ROOT,capture_output=True,text=True,timeout=20);assert busy.returncode==0,(busy.returncode,busy.stderr)
font=(ROOT/'runtime/native/font.inc').read_text();glyphs=[list(map(int,m.split(',')))for m in re.findall(r'\{([0-9,]+)\}',font)]
frame_bytes=busy_frame.read_bytes();label='A8 DSP OPEN E16 V0'
for n,c in enumerate(label):
 if c==' ':continue
 g=ord(c)-48 if '0'<=c<='9' else ord(c)-65+10
 for y in range(7):
  for x in range(5):
   if glyphs[g][y]&(1<<(4-x)):assert int.from_bytes(frame_bytes[((379+y)*240+8+n*6+x)*2:((379+y)*240+8+n*6+x)*2+2],'little')==0xffe0
report['busy_error_screen']={'passed':True,'label':label,'exit':busy.returncode,'first_failure_preserved_after_cleanup':True}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
