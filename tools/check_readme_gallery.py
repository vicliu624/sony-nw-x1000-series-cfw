"""Verify tracked README gallery links, dimensions and inventory without Pillow."""
from pathlib import Path
import hashlib,json,re,struct
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'docs/images';manifest=json.loads((folder/'manifest.json').read_text())
assert manifest['account_data'] is False and manifest['physical_device_capture'] is False
readme=(ROOT/'README.md').read_text();images=set(re.findall(r'!\[[^\]]*\]\((docs/images/[^)]+)\)',readme))
assert images=={'docs/images/'+entry['file'] for entry in manifest['images']}
for entry in manifest['images']:
    path=folder/entry['file'];assert path.parent==folder and path.suffix=='.png'
    data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
    assert hashlib.sha256(data).hexdigest()==entry['sha256']
    width,height=struct.unpack('>II',data[16:24]);assert 200<=width<=1200 and 200<=height<=1200
    assert len(data)<600000
print(json.dumps({'passed':True,'readme_images':len(images),'total_bytes':sum((folder/x['file']).stat().st_size for x in manifest['images']),'device_accessed':False}))
