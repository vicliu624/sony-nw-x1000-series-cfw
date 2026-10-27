"""Select pinned ordinary rootfs members into a new project work directory."""
import argparse,gzip,io,json,hashlib,tarfile
from pathlib import Path
from upg import unpack
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--upg',type=Path,default=ROOT/'work/updater-jp/NW_WM_FW.UPG');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.relative_to(ROOT/'work');out.mkdir(parents=True,exist_ok=False)
    parts=unpack(args.upg.read_bytes())[1]
    with gzip.GzipFile(fileobj=io.BytesIO(parts[3]))as stream:data=stream.read(256*1024*1024+1)
    if len(data)>256*1024*1024:raise ValueError('Archive too large')
    targets=json.loads((ROOT/'sources/native-targets.json').read_text());wanted={v['archive_path']:k for k,v in targets.items()};found=[]
    with tarfile.open(fileobj=io.BytesIO(data))as t:
        for m in t:
            if m.name not in wanted:continue
            if not m.isfile()or m.size>16*1024*1024:raise ValueError('Invalid analysis target')
            name=wanted[m.name];b=t.extractfile(m).read()
            if hashlib.sha256(b).hexdigest()!=targets[name]['sha256']:raise ValueError('Target hash mismatch: '+name)
            (out/name).write_bytes(b);found.append(name)
    if set(found)!=set(targets):raise ValueError('Missing target')
    print('Selected and hash-verified '+str(len(found))+' analysis targets; no Sony code executed')
if __name__=='__main__':main()
