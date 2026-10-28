"""Publish a small, reproducible set of credential-free program-rendered images.

Optional PC-only Pillow13.0.0. Native render/test tools create the source frames;
this tool converts RGB565 and lays out contact sheets. No live account/device IO.
"""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/images';OUT.mkdir(exist_ok=True)
records=[]
def source(path):
    path=ROOT/path;data=path.read_bytes()
    return path,data,{'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(data).hexdigest()}
def read_frame(path):
    p,data,record=source(path)
    if p.suffix!='.rgb565':return Image.open(p).convert('RGB'),record
    assert len(data)==240*432*2;image=Image.new('RGB',(240,432));colors=[]
    for at in range(0,len(data),2):
        pixel=int.from_bytes(data[at:at+2],'little');colors.append((((pixel>>11)&31)*255//31,((pixel>>5)&63)*255//63,(pixel&31)*255//31))
    image.putdata(colors);return image,record
def sheet(name,frames,kind):
    image=Image.new('RGB',(24+264*len(frames),492),'#e7edf1');draw=ImageDraw.Draw(image);inputs=[]
    for i,(label,path) in enumerate(frames):
        frame,record=read_frame(path);assert frame.size==(240,432)
        image.paste(frame,(24+264*i,40));draw.text((24+264*i,14),label,fill='#253f53');inputs.append(record)
    target=OUT/name;image.save(target,optimize=True)
    records.append({'file':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'kind':kind,'inputs':inputs})
def main():
    sheet('launcher-market.png',[(f'Applications / {i}',f'work/launcher-showcase/launcher-{i}.png') for i in (1,2,3)]+[('App Market','work/launcher-showcase/market.png')],'Actual launcher ARM framebuffer; shared market painter; example app packages/versions')
    sheet('market-details.png',[('About','work/market-details-preview/1.png'),('Changes','work/market-details-preview/2.png'),('Update','work/market-details-preview/3.png'),('Downgrade confirmation','work/market-details-preview/4.png')],'Actual ARM detail painter; synthetic version states')
    sheet('qqmusic.png',[('Collections','work/qqmusic-ui-native/frames/page-0-0.rgb565'),('Song list','work/qqmusic-ui-native/frames/page-1-0.rgb565'),('Track & quality','work/qqmusic-ui-native/frames/page-2-0.rgb565'),('Conversion progress','work/qqmusic-ui-native/frames/import-active-2.rgb565')],'Actual QQ Music ARM framebuffer; synthetic account, songs and import state')
    sheet('pocket-fm.png',[('Tuning','work/fm-radio-review/tuning.png'),('Presets','work/fm-radio-review/favorites.png'),('Direct frequency entry','work/fm-radio-review/keypad.png')],'Actual native FM framebuffer fixtures; no RF/audio reception claim')
    icons=sorted((ROOT/'runtime/apps').glob('*/assets/icon.png'))
    image=Image.new('RGB',(800,((len(icons)+3)//4)*116+16),'#e7edf1');draw=ImageDraw.Draw(image);inputs=[]
    for i,p in enumerate(icons):
        tile=Image.open(p).convert('RGBA');x=24+(i%4)*194;y=16+(i//4)*116;image.paste(tile,(x,y),tile);draw.text((x,y+72),p.parent.parent.name,fill='#253f53');inputs.append(source(p.relative_to(ROOT))[2])
    image.save(OUT/'app-icons.png',optimize=True)
    records.append({'file':'app-icons.png','sha256':hashlib.sha256((OUT/'app-icons.png').read_bytes()).hexdigest(),'kind':'Original vector-derived app icon set','inputs':inputs})
    (OUT/'manifest.json').write_text(json.dumps({'account_data':False,'physical_device_capture':False,'images':records},indent=2)+'\n')
    print(json.dumps({'documentation_images':len(records),'output':str(OUT)},indent=2))
if __name__=='__main__':main()
