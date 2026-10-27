"""Analyze local extracted resources and export 32-bit icons; no firmware modification."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
from resources import parse_stx,parse_tgp

ROOT=Path(__file__).resolve().parents[1]

def png_bgra(width,height,data):
    def chunk(kind,body):
        return struct.pack(">I",len(body))+kind+body+struct.pack(">I",zlib.crc32(kind+body)&0xffffffff)
    rgba=bytearray(data)
    rgba[0::4],rgba[2::4]=data[2::4],data[0::4]
    scan=b"".join(b"\0"+rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,6,0,0,0))+chunk(b"IDAT",zlib.compress(scan))+chunk(b"IEND",b"")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--resources",type=Path,default=ROOT/"work/resource-analysis")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.relative_to(ROOT/"work");out.mkdir(parents=True,exist_ok=False)
    texts={p.stem.rsplit("-",1)[-1]:parse_stx(p.read_bytes())for p in args.resources.glob("*.stx")}
    jp=texts["jp"]
    stats={}
    for language,items in texts.items():
        if len(items)!=len(jp):raise ValueError("Language index mismatch")
        stats[language]={"records":len(items),"nonempty":sum(bool(t)for t in items),"missing_where_jp_nonempty":sum(bool(a)and not b for a,b in zip(jp,items))}
    groups={p.name:parse_tgp(p.read_bytes())for p in sorted(args.resources.glob("TEXGRP*.DAT"))}
    icons=[];data=(args.resources/"TEXGRP00.DAT").read_bytes()
    labels=["FM","TV","YouTube","Photos","Music","Video","NC","Podcasts","Browser","Settings"]
    for index,label in enumerate(labels,54):
        rec=groups["TEXGRP00.DAT"][index]
        if (rec["width"],rec["height"],rec["format"])!=(64,64,16):raise ValueError("Icon profile mismatch")
        start=rec["offset"]+32;raw=data[start:start+rec["bytes"]]
        (out/f"home-{index:03}-{label}.png").write_bytes(png_bgra(64,64,raw))
        icons.append(dict(rec,label=label))
    result={"scope":"offline resources; no language patch or device test","languages":stats,"texture_count":sum(len(v)for v in groups.values()),"groups":groups,"home_icon_artwork":icons,"inputs":{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in args.resources.iterdir()if p.suffix.lower()in (".stx",".dat")}}
    (out/"resource-report.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"languages":stats,"texture_count":result["texture_count"],"home_icons":len(icons)},indent=2))
if __name__=="__main__":main()
