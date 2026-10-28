"""Create bounded device presentation resources from app-local metadata and PNG."""
import json,struct
from pathlib import Path
from app_registry import ROOT,applications

def presentation(ident):
    from PIL import Image
    info=applications()[ident]
    with Image.open(ROOT/'runtime/apps'/ident/'assets/icon.png') as source:
        image=source.convert('RGBA').resize((36,36),Image.Resampling.LANCZOS)
    pixels=[0 if a<128 else max(1,((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b,a in image.getdata()]
    def field(value,n):return value.encode('ascii').ljust(n,b'\0')
    return b'HBART001'+field(info['title'],49)+field(info['summary'],97)+struct.pack('<1296H',*pixels)

def install_presentation(ident,folder,version):
    import shutil
    folder=Path(folder);info=applications()[ident]
    (folder/'presentation.bin').write_bytes(presentation(ident))
    (folder/'app-info.json').write_text(json.dumps({k:info[k] for k in ('id','title','summary','description','changes','channel')}|{'version':version},indent=2)+'\n')
    for name in ('icon.png','icon.svg'):
        source=ROOT/'runtime/apps'/ident/'assets'/name
        if source.is_file():shutil.copyfile(source,folder/name)
