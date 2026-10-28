"""Render actual ARM details painter in QEMU, never opens player hardware."""
from pathlib import Path
import argparse,json,os,subprocess
from PIL import Image,ImageDraw
from market_metadata import descriptions
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',default='fm-radio',choices=sorted(descriptions()));parser.add_argument('--output',type=Path,default=ROOT/'work/market-details-preview');parser.add_argument('--payload-bytes',type=int,default=212000);options=parser.parse_args()
work=options.output.resolve()
if not work.is_relative_to(ROOT/'work') or work==ROOT/'work':raise ValueError('Output must be under work/')
work.mkdir(exist_ok=True);info=descriptions()[options.app]
app_version=(ROOT/'runtime/apps/pet/VERSION').read_text().strip() if options.app=='pet' else '0.1.0-dev.21'
source='''#include "runtime/store/market_detail.h"
#include "runtime/store/canvas.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned short pixels[240*432];
int main(int argc,char **argv){if(argc!=4)return 64;struct hb_remote_entry e={0};struct hb_market_local local={0};
'''
for field,value in dict(id=options.app,version=app_version,**{k:info[k] for k in ('title','summary','description','changes','channel')}).items():source+=f'strcpy(e.{field},{json.dumps(value)});\n'
source+=f'e.download_bytes={max(0,options.payload_bytes)};'
source+='''local.status=(enum hb_market_status)atoi(argv[1]);local.present=local.status!=HB_MARKET_NEW;if(local.present)strcpy(local.version,local.status==HB_MARKET_DOWNGRADE?"0.3.0":"0.1.0-dev.20");
struct hb_store_canvas canvas;struct hb_store_painter painter;if(hb_store_canvas_init(&canvas,pixels,240*432,&painter))return 1;
hb_market_detail_draw(&e,&local,(unsigned)atoi(argv[2]),0,atoi(argv[3]),&painter);
return fwrite(pixels,1,sizeof pixels,stdout)==sizeof pixels?0:2;}
'''
(work/'preview.c').write_text(source);lib=ROOT/'work/arm-signal-tests/lib';app=work/'preview.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-D_DEFAULT_SOURCE','-Os','-Wall','-Wextra','-Werror','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-I'+str(ROOT),'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',str(work/'preview.c'),'runtime/store/canvas.c','tools/stock_test_start.c','tools/store_link_start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],check=True)
sheet=Image.new('RGB',(1080,492),'#e7edf1');d=ImageDraw.Draw(sheet)
for n,(label,status,tab,confirm) in enumerate([('About / install',0,0,0),('Changes',0,1,0),('Update available',2,0,0),('Downgrade confirmation',3,0,1)]):
    raw=subprocess.check_output(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),str(status),str(tab),str(confirm)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),timeout=15)
    assert len(raw)==240*432*2
    image=Image.new('RGB',(240,432));colors=[]
    for i in range(0,len(raw),2):
        value=int.from_bytes(raw[i:i+2],'little');colors.append((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
    image.putdata(colors);image.save(work/(str(n+1)+'.png'));sheet.paste(image,(24+n*264,40));d.text((24+n*264,14),label,fill='#253f53')
sheet.save(work/'overview.png');print(work/'overview.png')
