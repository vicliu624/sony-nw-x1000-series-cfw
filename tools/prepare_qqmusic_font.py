"""Acquire official pinned OFL font and matching stb rasterizer header; no install."""
from pathlib import Path
import hashlib,json,shutil,urllib.request
ROOT=Path(__file__).resolve().parents[1]
revision='f8d157532fbfaeda587e826d4cd5b21a49186f7c'
work=ROOT/'work/qqmusic-font';work.mkdir(exist_ok=True)
files={}
for path,name in [('Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf','NotoSansCJKsc-Regular.otf'),('Sans/LICENSE','OFL.txt')]:
    url=f'https://raw.githubusercontent.com/notofonts/noto-cjk/{revision}/{path}'
    out=work/name
    if not out.exists():
        data=urllib.request.urlopen(url,timeout=60).read(33554433)
        if not data or len(data)>33554432:raise ValueError('Font resource size limit')
        out.write_bytes(data)
    files[name]={'url':url,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
stb=ROOT/'work/image-upstream/stb/stb_truetype.h';dest=ROOT/'third_party/qqmusic-stb/stb_truetype.h'
if not dest.exists():shutil.copyfile(stb,dest)
assert dest.read_bytes()==stb.read_bytes()
manifest=ROOT/'sources/qqmusic-image-sources.json';source=json.loads(manifest.read_text())
source['files']['stb_truetype.h']=hashlib.sha256(dest.read_bytes()).hexdigest();manifest.write_text(json.dumps(source,indent=2)+'\n')
shutil.copyfile(work/'OFL.txt',ROOT/'third_party/qqmusic-stb/Noto-OFL.txt')
report={'font_origin':'https://github.com/notofonts/noto-cjk','revision':revision,'files':files,'device_install':False,'runtime_policy':'External user-storage resource; never system font installation.'}
(ROOT/'sources/qqmusic-font-source.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
