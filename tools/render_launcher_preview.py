"""Render the actual ARM launcher and shared market painter without a device.

Optional design dependency: Pillow 13.0.0. Outputs remain in ignored work/.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launcher',type=Path,default=ROOT/'work/launcher-icons-review/launcher.elf')
    p.add_argument('--showcase',action='store_true',help='Exclude the long-name test app for documentation.')
    a=p.parse_args();work=ROOT/('work/launcher-showcase' if a.showcase else 'work/launcher-icons-preview');work.mkdir(exist_ok=True)
    apps=work/'apps';apps.mkdir(exist_ok=True)
    executable=(ROOT/'work/hello-app/package/app').read_bytes()
    entries=[('store','App Market'),('fm-radio','Pocket FM'),('qqmusic','QQ Music'),('qqcheck','QQ Startup Check'),('ebook','EBook'),('dictionary','Dictionary'),('terminal','WiFi Terminal'),('device-info','Device Info'),('language','Language'),('gbc','Game Boy Color'),('tamagotchi-id','Tamagotchi iD'),('pet','BSOD Pet'),('graphics-demo','Graphics'),('diagnostics','Device Check'),('key-check','Key Check'),('hello','Hello')]
    if not a.showcase:entries.append(('custom-app','A very long custom application title'))
    for ident,name in entries:
        folder=apps/ident;folder.mkdir(exist_ok=True);(folder/'app').write_bytes(executable)
        (folder/'app.ini').write_text(f'api=1\nid={ident}\nname={name}\nversion=1.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(executable)}\nsha256={hashlib.sha256(executable).hexdigest()}\n')
    from app_presentation import install_presentation
    from app_registry import applications
    for ident in applications():
        if (apps/ident).is_dir():install_presentation(ident,apps/ident,'1.0.0')
    lib=ROOT/'work/arm-signal-tests/lib'
    command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(a.launcher),'--render',str(apps)]
    env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    def decode(raw):
        assert len(raw)==240*432*2
        out=Image.new('RGB',(240,432));colors=[]
        for i in range(0,len(raw),2):
            v=int.from_bytes(raw[i:i+2],'little');colors.append((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
        out.putdata(colors);return out
    shots=[]
    for page in range(3):
        raw=subprocess.check_output(command+[str(page)],env=env,timeout=15)
        image=decode(raw);image.save(work/f'launcher-{page+1}.png');shots.append(image)
    # Compile the real market drawing path, with ordinary in-memory catalog data.
    fixture=work/'market-preview.c'
    fixture.write_text('''#include "runtime/store/remote_list.h"
#include "runtime/store/canvas.h"
#include <stdio.h>
#include <string.h>
static unsigned short pixels[240*432];
int main(void){struct hb_remote_catalog c={0};struct hb_remote_list list;
struct hb_store_canvas canvas;struct hb_store_painter painter;
const char *ids[]={__IDS__};
c.valid=1;c.count=sizeof ids/sizeof ids[0];for(unsigned i=0;i<c.count;i++){strcpy(c.entries[i].id,ids[i]);strcpy(c.entries[i].version,"0.1.0-dev.20");}
if(hb_store_canvas_init(&canvas,pixels,240*432,&painter)||hb_remote_list_init(&list,&c,"store")||hb_remote_list_draw(&list,&c,&painter))return 1;
return fwrite(pixels,1,sizeof pixels,stdout)==sizeof pixels?0:2;}
'''.replace('__IDS__',','.join(json.dumps(ident) for ident,_ in entries)))
    exe=work/'market-preview'
    subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-I'+str(ROOT),str(fixture),'runtime/store/remote_list.c','runtime/store/canvas.c','runtime/native/frontend.c','-o',str(exe)],cwd=ROOT,check=True)
    image=decode(subprocess.check_output([str(exe)],timeout=10));image.save(work/'market.png');shots.append(image)
    sheet=Image.new('RGB',(4*264+24,492),'#e7edf1');d=ImageDraw.Draw(sheet)
    for n,(image,title) in enumerate(zip(shots,['Applications / 1','Applications / 2','Applications / 3','App Market'])):
        x=24+n*264;d.text((x,14),title,fill='#253f53');sheet.paste(image,(x,40))
    sheet.save(work/'overview.png')
    print(work/'overview.png')

if __name__=='__main__':main()
