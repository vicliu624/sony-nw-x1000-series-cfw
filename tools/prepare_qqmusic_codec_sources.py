"""Vendor selected official source files already acquired under work/; no network."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
revisions={'tremor':'820fb3237ea81af44c9cc468c8b4e20128e3e5ad','ogg':'06a5e0262cdc28aa4ae6797627a783b5010440f0','shine':'ab5e3526b64af1a2eaa43aa6f441a7312e013519'}
origins={'tremor':'https://gitlab.xiph.org/xiph/tremor.git','ogg':'https://gitlab.xiph.org/xiph/ogg.git','shine':'https://github.com/toots/shine.git'}
destination=ROOT/'third_party/qqmusic-codecs'
if destination.exists():raise FileExistsError('Codec source directory already exists; review/update explicitly')
rows={}
for name,rev in revisions.items():
    src=ROOT/'work/codec-upstream'/name
    assert subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()==rev
    if name=='tremor':files=list(src.glob('*.c'))+list(src.glob('*.h'))
    elif name=='ogg':files=list((src/'src').glob('*.c'))+list((src/'src').glob('*.h'))+list((src/'include/ogg').glob('*.h'))+list((src/'include/ogg').glob('*.in'))
    else:files=list((src/'src/lib').glob('*.c'))+list((src/'src/lib').glob('*.h'))
    files += [p for p in [src/'COPYING',src/'README',src/'README.md',src/'README.old',src/'AUTHORS'] if p.is_file()]
    records={}
    for path in files:
        relative=path.relative_to(src);out=destination/name/relative;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,out)
        records[relative.as_posix()]={'upstream_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    rows[name]={'origin':origins[name],'revision':rev,'files':records}
# Explicit portable C selection; do not add codec inline assembly on player.
types=destination/'shine/src/lib/types.h'
text=types.read_text();text=text.replace('#if defined(__mips__) && (__mips == 32)','#if !defined(QQ_CODEC_PORTABLE_C) && defined(__mips__) && (__mips == 32)').replace('#elif defined(__arm__) && !defined(__thumb__)','#elif !defined(QQ_CODEC_PORTABLE_C) && defined(__arm__) && !defined(__thumb__)')
types.write_text(text)
for name,row in rows.items():
    for relative,record in row['files'].items():record['vendored_sha256']=hashlib.sha256((destination/name/relative).read_bytes()).hexdigest()
report={'sources':rows,'local_changes':['shine types.h: QQ_CODEC_PORTABLE_C selects existing generic C multiply backend'],
        'network_scope':'Official source acquisition explicitly authorized; builds/tests offline.',
        'device_access':False,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'sources/qqmusic-codec-sources.json').write_text(json.dumps(report,indent=2)+'\n')
print('Vendored official codec source files:',sum(len(r['files']) for r in rows.values()))
