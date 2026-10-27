"""External homebrew list for the native front end. Reads ordinary user-storage files.
No Sony configuration edits, process execution, firmware or partition operations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct

MAX_APPS=32
MAX_MANIFEST_BYTES=1024
MAX_NAME_BYTES=48
MAX_VERSION_BYTES=32
FIELDS={"api","id","name","version","target","exec","bytes","sha256"}

def regular(path,directory=False):
    s=path.lstat()
    if not (stat.S_ISDIR(s.st_mode)if directory else stat.S_ISREG(s.st_mode)):raise ValueError("Not an ordinary file/directory")
    return s

def read_app(folder):
    regular(folder,True)
    if not re.fullmatch("[a-z0-9][a-z0-9-]{0,31}",folder.name):raise ValueError("Invalid ID")
    p=folder/"app.ini";s=regular(p)
    if s.st_size>MAX_MANIFEST_BYTES:raise ValueError("Manifest too large for native launcher")
    fields={}
    # Match the native LF parser; universal-newline decoding also accepts bare CR.
    lines=p.read_bytes().decode("utf-8").split("\n")
    if lines[-1]=="":lines.pop()
    for line in lines:
        if line.endswith("\r"):line=line[:-1]
        if not line or "="not in line:raise ValueError("Invalid manifest line")
        k,v=line.split("=",1)
        if k in fields:raise ValueError("Duplicate key")
        fields[k]=v
    if set(fields)!=FIELDS or fields["api"]!="1" or fields["id"]!=folder.name or fields["target"]!="sony-nw-x1000-jp" or fields["exec"]!="app":raise ValueError("Unsupported app contract")
    if len(fields["version"].encode("utf-8"))>MAX_VERSION_BYTES or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?",fields["version"]):raise ValueError("Invalid version")
    if not 1<=len(fields["name"].encode("utf-8"))<=MAX_NAME_BYTES or any(ord(c)<32 for c in fields["name"]):raise ValueError("Invalid name")
    if not fields["bytes"].isdigit()or not 84<=int(fields["bytes"])<=128*1024*1024:raise ValueError("Invalid byte count")
    if not re.fullmatch("[a-f0-9]{64}",fields["sha256"]):raise ValueError("Invalid SHA-256")
    p=folder/"app";s=regular(p)
    if s.st_size!=int(fields["bytes"]):raise ValueError("Size mismatch")
    digest=hashlib.sha256()
    with p.open("rb")as stream:
        head=stream.read(52);digest.update(head)
        while b:=stream.read(65536):digest.update(b)
    if digest.hexdigest()!=fields["sha256"]:raise ValueError("Hash mismatch")
    if head[:7]!=b"\x7fELF\x01\x01\x01"or struct.unpack_from("<HH",head,16)!=(2,40):raise ValueError("Not ARM32 little-endian executable")
    # Actual Sony-kernel ELF and ABI qualification is a separate build check.
    return {"id":fields["id"],"name":fields["name"],"version":fields["version"],"program":str(p),"bytes":s.st_size,"sha256":fields["sha256"]}

def scan(root):
    regular(root,True);paths=[]
    for p in root.iterdir():
        if len(paths)>=64:raise ValueError("Too many directory entries")
        paths.append(p)
    apps=[];rejected=[]
    for p in sorted(paths):
        if p.name.startswith("."):continue
        if len(apps)+len(rejected)>=MAX_APPS:raise ValueError("Too many app candidates")
        try:apps.append(read_app(p))
        except (OSError,ValueError,UnicodeError)as e:rejected.append({"id":p.name,"reason":str(e)})
    apps.sort(key=lambda a:(a["id"]!="store",a["name"].casefold(),a["id"]))
    return {"apps":apps,"rejected":rejected,"store_installed":any(a["id"]=="store"for a in apps),"return_to_walkman":True,"sony_menu_registration":"front-end only; individual apps are not registered"}
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("apps",type=Path);args=p.parse_args();print(json.dumps(scan(args.apps),ensure_ascii=False,indent=2))
