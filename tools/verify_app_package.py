"""Validate complete native app packages offline; never accesses a player."""
import argparse,hashlib,json,re
from pathlib import Path,PurePosixPath
from app_registry import applications

def verify(folder):
    folder=Path(folder);entries={}
    if folder.is_symlink():raise ValueError('Linked package root')
    for p in folder.rglob('*'):
        if p.is_symlink():raise ValueError('Linked package file')
        if p.is_file() and p.name!='files.sha256':entries[p.relative_to(folder).as_posix()]=p.read_bytes()
    if not {'app','app.ini','app-info.json','presentation.bin','icon.png'}<=set(entries):raise ValueError('Incomplete application package')
    lines=(folder/'files.sha256').read_text().splitlines()
    if not lines or lines[0]!='HBFILES1':raise ValueError('Inventory header')
    seen=set()
    for line in lines[1:]:
        digest,size,name=line.split(' ')
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or name in seen or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Unsafe inventory')
        seen.add(name);data=entries[name]
        if len(data)!=int(size) or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Inventory mismatch: '+name)
    if seen!=set(entries):raise ValueError('Unindexed package file')
    manifest=dict(line.split('=',1) for line in entries['app.ini'].decode('ascii').splitlines())
    if set(manifest)!={'api','id','name','version','target','exec','bytes','sha256'} or manifest['api']!='1' or manifest['exec']!='app' or manifest['target']!='sony-nw-x1000-jp':raise ValueError('Manifest contract')
    app=entries['app']
    if app[:6]!=b'\x7fELF\x01\x01' or int.from_bytes(app[18:20],'little')!=40:raise ValueError('ARM ELF')
    if int(manifest['bytes'])!=len(app) or manifest['sha256']!=hashlib.sha256(app).hexdigest():raise ValueError('Executable identity')
    info=json.loads(entries['app-info.json'])
    if info['id']!=manifest['id'] or info['version']!=manifest['version']:raise ValueError('Metadata identity')
    binary=entries['presentation.bin']
    if len(binary)!=2746 or binary[:8]!=b'HBART001':raise ValueError('Presentation format')
    if binary[8:57].rstrip(b'\0').decode('ascii')!=info['title'] or binary[57:154].rstrip(b'\0').decode('ascii')!=info['summary']:raise ValueError('Presentation metadata')
    definition=applications().get(info['id'])
    if definition:
        for row in definition.get('package_files',[]):
            if row['destination'] not in entries:raise ValueError('Required resource absent: '+row['destination'])
    return {'id':info['id'],'version':info['version'],'files':len(entries),'passed':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('packages',nargs='+',type=Path);args=p.parse_args()
    print(json.dumps([verify(folder) for folder in args.packages],indent=2))
if __name__=='__main__':main()
