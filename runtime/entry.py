"""Host-side external-app entry prototype. Execution is deliberately unavailable.

This scans ordinary files and builds a sandbox plan. It never mounts, writes,
spawns app code, edits AppList.conf or accepts a user-supplied readiness flag.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct

REQUIRED={"schema","id","name","target","executable","bytes","sha256","data_quota_bytes"}
MAX_APPS=32
MAX_PROGRAM=2*1024*1024
DEVICE_EXECUTION_AVAILABLE=False
BLOCKERS=("Full X1000 isolation syscall implementations not qualified", "Live mount and device permissions unobserved", "Sony appproxy lifecycle and USB handoff unimplemented", "Device framebuffer/input broker not implemented", "Old-kernel isolation path and privileged IPC exposure not qualified")

def object_no_duplicates(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError("Duplicate manifest key")
        result[k]=v
    return result

def ordinary(path,directory=False):
    mode=path.lstat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise ValueError("Symlinks and special files are not allowed")

def inspect_app(folder):
    ordinary(folder,True)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}",folder.name):raise ValueError("Invalid application ID")
    manifest=folder/"app.json";ordinary(manifest)
    if manifest.stat().st_size>4096:raise ValueError("Manifest too large")
    value=json.loads(manifest.read_text(encoding="utf-8"),object_pairs_hook=object_no_duplicates)
    if not isinstance(value,dict)or set(value)!=REQUIRED:raise ValueError("Unexpected manifest fields")
    if type(value["schema"])is not int or value["schema"]!=1 or value["id"]!=folder.name or value["target"]!="sony-nw-x1000-jp" or value["executable"]!="app":raise ValueError("Unsupported application contract")
    if not isinstance(value["name"],str)or not 1<=len(value["name"])<=48 or any(ord(c)<32 for c in value["name"]):raise ValueError("Invalid display name")
    if type(value["bytes"])is not int or not 52<=value["bytes"]<=MAX_PROGRAM:raise ValueError("Program size out of range")
    if type(value["data_quota_bytes"])is not int or not 65536<=value["data_quota_bytes"]<=1048576:raise ValueError("Data quota out of range")
    if not isinstance(value["sha256"],str)or not re.fullmatch("[0-9a-f]{64}",value["sha256"]):raise ValueError("Invalid digest")
    program=folder/"app";ordinary(program)
    if program.stat().st_size!=value["bytes"]:raise ValueError("Program length mismatch")
    data=program.read_bytes()
    if hashlib.sha256(data).hexdigest()!=value["sha256"]:raise ValueError("Program hash mismatch")
    if data[:7]!=b"\x7fELF\x01\x01\x01" or struct.unpack_from("<H",data,18)[0]!=40:raise ValueError("Not ARM32 little-endian ELF")
    # Header recognition is not executable admission or old-kernel ABI validation.
    return value

def discover(root):
    ordinary(root,True)
    apps=[];errors=[];count=0
    bounded=[]
    for path in root.iterdir():
        if len(bounded)>=64:raise ValueError("Too many directory entries")
        bounded.append(path)
    for path in sorted(bounded):
        if path.name.startswith("."):continue
        count+=1
        if count>MAX_APPS:raise ValueError("Too many application entries")
        try:apps.append(inspect_app(path))
        except (OSError,ValueError,UnicodeError)as e:errors.append({"id":path.name,"error":str(e)})
    return {"apps":apps,"rejected":errors,"return_to_sony":True,"device_execution_available":False}

def plan(app):
    return {"id":app["id"],"status":"blocked-before-execution","blockers":list(BLOCKERS),"draft_policy":{"identity":"dedicated unprivileged UID/GID; not the shared browser user","root":"private read-only staged root; no host root bind","writable_data":{"bounded_tmpfs_bytes":app["data_quota_bytes"],"persistence":"not implemented; must use bounded trusted save broker"},"devices":"none; future display/input broker over inherited bounded pipes","exposed_proc_sys_devfs":False,"capabilities":"clear groups and all UID/GID IDs, verify no capabilities, no set-ID files","inherited_fds":"only explicit broker pipes; close other descriptors","limits":"per-file, inode, address space, process count, CPU and wall time","usb":"must fail closed until handoff verified"},"firmware_changes":False}

def launch(app):
    raise RuntimeError("Device execution is disabled: "+"; ".join(BLOCKERS))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apps",required=True,type=Path)
    action=p.add_mutually_exclusive_group();action.add_argument("--plan");action.add_argument("--launch")
    args=p.parse_args();result=discover(args.apps)
    selected=args.plan or args.launch
    if selected:
        found=next((a for a in result["apps"]if a["id"]==selected),None)
        if found is None:p.error("Application is absent or invalid")
        if args.launch:
            try:launch(found)
            except RuntimeError as e:p.exit(3,str(e)+"\n")
        result=plan(found)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
