"""Bounded metadata inventory; never extract arbitrary tar paths or execute inputs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from upg import unpack

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upg", type=Path, default=ROOT/"work/updater-jp/NW_WM_FW.UPG")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT/"work")
    out.mkdir(parents=True, exist_ok=False)
    entries, parts = unpack(args.upg.read_bytes())
    with gzip.GzipFile(fileobj=io.BytesIO(parts[3])) as stream:
        raw = stream.read(256*1024*1024+1)
    if len(raw) > 256*1024*1024:
        raise ValueError("Root archive exceeds inspection limit")
    rows=[]
    selected={"./etc/init.d/gemini":"gemini-init.sh.txt", "./etc/init.d/icx1087driver":"driver-init.sh.txt", "./etc/firmversion":"firmversion.txt", "./usr/local/bin/sysmgr.sh":"sysmgr.sh.txt"}
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for i,m in enumerate(tar):
            if i >= 10000:
                raise ValueError("Too many archive members")
            row={"name":m.name,"size":m.size,"mode":oct(m.mode),"uid":m.uid,"gid":m.gid,"type":m.type.decode("ascii","replace"),"link":m.linkname}
            if m.isfile():
                if m.size > 64*1024*1024:
                    raise ValueError("Oversized member")
                data=tar.extractfile(m).read()
                row["sha256"]=hashlib.sha256(data).hexdigest()
                if m.name in selected:
                    (out/selected[m.name]).write_bytes(data)
            rows.append(row)
    (out/"upgrade-script.sh.txt").write_bytes(parts[0])
    report={"scope":"offline metadata only; no execution or device access", "components":[{"index":i,"offset":o,"bytes":n,"sha256":hashlib.sha256(parts[i]).hexdigest()}for i,(o,n) in enumerate(entries)],"rootfs_tar_bytes":len(raw),"rootfs_entries":len(rows),"regular_file_bytes":sum(m["size"] for m in rows if m["type"] in ("0","\u0000")),"files":rows}
    (out/"inventory.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="files"},indent=2))

if __name__ == "__main__":
    main()
