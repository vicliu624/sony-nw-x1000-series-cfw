"""Record reviewed codec changes against retained official upstream hashes."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'sources/qqmusic-codec-sources.json';data=json.loads(path.read_text())
allowed={('shine','src/lib/types.h'),('shine','src/lib/layer3.c')}
for name,row in data['sources'].items():
    for relative,record in row['files'].items():
        original=ROOT/'work/codec-upstream'/name/relative
        assert hashlib.sha256(original.read_bytes()).hexdigest()==record['upstream_sha256']
        digest=hashlib.sha256((ROOT/'third_party/qqmusic-codecs'/name/relative).read_bytes()).hexdigest()
        if (name,relative) not in allowed:assert digest==record['vendored_sha256']
        record['vendored_sha256']=digest
data['local_changes']=['shine types.h: explicit portable C backend',
 'shine layer3.c: exact integer frame-slot calculation, avoid integral-rate floating rounding',
 'shine layer3.c: flush final byte-aligned cache bytes, reject inconsistent bit tail']
data['patch_recorder_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
path.write_text(json.dumps(data,indent=2)+'\n')
