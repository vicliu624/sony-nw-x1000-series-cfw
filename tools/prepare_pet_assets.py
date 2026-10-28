"""Convert a user-supplied BSOD v2 sheet to bounded device sprite records.

Computer-side asset conversion only. The original artwork is not included in Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def convert(source, output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / 'work'):
        raise ValueError('Output must be under project work/')
    im = Image.open(source).convert('RGBA')
    if im.size != (1536, 2288):
        raise ValueError('Expected v2 BSOD sheet: 1536 x 2288')
    output.mkdir(parents=True, exist_ok=True)
    data = bytearray()
    # Preserve all nine animation rows; look-direction rows are not needed.
    for row in range(9):
        for col in range(8):
            frame = im.crop((col*192,row*208,(col+1)*192,(row+1)*208))
            frame = frame.resize((96,104), Image.Resampling.LANCZOS)
            for r,g,b,a in frame.getdata():
                pixel = (r>>3)<<11 | (g>>2)<<5 | (b>>3)
                data.extend((pixel&255,pixel>>8,a))
    (output/'sprites.bin').write_bytes(data)
    report = {'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
              'format':'9 rows x 8 frames x 96 x 104 x RGB565LE-alpha8',
              'redistribution_license_established':False}
    (output/'assets.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/pet-review/assets')
    args=parser.parse_args()
    print(json.dumps(convert(args.source,args.output),indent=2))
