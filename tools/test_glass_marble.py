"""Real shared physics/codec/renderer on host and ARM926; no radio or devices."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/glass-marble-tests';OUT.mkdir(exist_ok=True)
sources=['tools/fixtures/glass_marble.c','runtime/apps/glass-marble/marble.c']
def run(args,**kw):return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,**kw)
run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*sources,'-lm','-o',OUT/'test'])
host=run([OUT/'test'],capture_output=True,text=True).stdout
lib=ROOT/'work/arm-signal-tests/lib';stock=ROOT/'work/stock-resolver-probe'
run(['arm-linux-gnueabi-gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',stock/'libm.so.6',lib/'libc.so.6',lib/'ld-linux.so.3','-lgcc','-o',OUT/'test.arm'])
arm=run(['qemu-arm','-cpu','arm926',lib/'ld-linux.so.3','--library-path',str(lib)+':'+str(stock),OUT/'test.arm'],capture_output=True,text=True).stdout
raw=subprocess.check_output([str(OUT/'test'),'--preview'],cwd=ROOT)
from PIL import Image,ImageDraw
def decode(raw,w,h):
 rgb=bytearray()
 for i in range(0,len(raw),2):
  v=raw[i]|raw[i+1]<<8;rgb.extend((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
 return Image.frombytes('RGB',(w,h),bytes(rgb))
m=decode(raw[:480*480*2],480,480);x=decode(raw[480*480*2:],240,432)
m.save(OUT/'mosaico.png');x.save(OUT/'x1060.png')
# Both panels are rescaled to the same physical pixels/mm for this desk view.
scale=8;image=Image.new('RGB',(760,620),'#131923');draw=ImageDraw.Draw(image)
draw.text((20,12),'GLASS MARBLE / SHARED PHYSICAL SPACE',fill='white')
image.paste(m.resize((320,320)),(20,150));image.paste(x.resize((296,533)),(404,44))
draw.text((20,490),'ESP-Mosaico 480 x 480',fill='white');draw.text((404,590),'X1060 240 x 432',fill='white')
draw.text((345,310),'gap',fill='#aab3c2');image.save(OUT/'paired-preview.png')
report={'passed':True,'host':host,'arm926_original_libc':arm,'packet_bytes':200,'device_accessed':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
