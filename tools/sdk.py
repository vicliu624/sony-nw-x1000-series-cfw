"""X1000 SDK: create, check, build, preview and package native apps. PC only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from app_registry import ROOT, applications
from sdk_build import LIBRARIES, compile_app, fresh_work

def create(ident,template,title=None):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,31}',ident):raise ValueError('Invalid app ID')
    if template not in ('minimal','touch-ui','canvas-game'):raise ValueError('Unknown template')
    title=title or ident.replace('-',' ').title()
    if not 1<=len(title)<=48 or any(ord(c)<32 or ord(c)>126 for c in title):raise ValueError('Title must be 1..48 printable ASCII characters')
    folder=ROOT/'runtime/apps'/ident
    if folder.exists() or folder.is_symlink():raise ValueError('Application already exists')
    if folder.parent.is_symlink():raise ValueError('Linked app root')
    folder.mkdir(parents=True);(folder/'assets').mkdir()
    # JSON quoting is also a valid C string for the permitted ASCII title.
    text=(ROOT/'sdk/templates'/template/'main.c').read_text().replace('"@ID@"',json.dumps(ident)).replace('"@TITLE@"',json.dumps(title))
    (folder/'main.c').write_text(text)
    version=(ROOT/'sdk/VERSION').read_text().strip()
    info={'schema':1,'id':ident,'target':'sony-nw-x1000-jp','title':title,'summary':'X1000 SDK '+template+' example',
          'description':'Experimental native application built with the X1000 SDK. Computer previews do not qualify device behavior.',
          'changes':'First experimental SDK application.','channel':'experimental',
          'build':{'script':'build.py','package':'work/sdk-builds/'+ident,'output_suffix':''}}
    (folder/'app.json').write_text(json.dumps(info,indent=2)+'\n')
    (folder/'VERSION').write_text('0.1.0-alpha.1\n')
    modules=['app','canvas']+(['storage'] if template=='touch-ui' else [])
    (folder/'build.json').write_text(json.dumps({'sdk':version,'modules':modules,'sources':['main.c']},indent=2)+'\n')
    (folder/'build.py').write_text('from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))\nfrom sdk_build import build\nif __name__ == "__main__":\n    build(Path(__file__).resolve().parent)\n')
    # Original, deliberately neutral placeholder artwork, generated without dependencies.
    rows=b''.join(b'\0'+b''.join(bytes((54,135,119,255 if 5<=x<59 and 5<=y<59 else 0)) for x in range(64)) for y in range(64))
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
    (folder/'assets/icon.png').write_bytes(png)
    (folder/'assets/icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="5" y="5" width="54" height="54" rx="12" fill="#368777"/></svg>\n')
    (folder/'README.md').write_text('# '+title+'\n\nGenerated '+template+' application. See [SDK guide](../../../docs/sdk/README.md).\n\nSource: main.c. Build: python tools/sdk.py build '+ident+'.\nPreview: python tools/sdk.py preview '+ident+'.\nTouch the on-screen button; Back to apps exits.\n'+
        ('State: HOMEBREW/data/'+ident+'/counter.bin, outside the replaceable package.\nDevice storage fails closed until an independently qualified ownership provider is supplied.\n' if template=='touch-ui' else 'No persistent state or networking.\n')+
        'Offline entry checks: --help, --version, --selftest. Preview is not hardware qualification.\n')
    print('Created '+str(folder.relative_to(ROOT))+' (not added to the public release allowlist)')
    return folder

def doctor():
    rows=[]
    for tool in ('gcc','sdl2-config','arm-linux-gnueabi-gcc','qemu-arm','7z'):
        rows.append({'component':tool,'ready':shutil.which(tool) is not None})
    for name in ('PIL','elftools','Crypto'):
        rows.append({'component':name,'ready':importlib.util.find_spec(name) is not None})
    for name,digest in LIBRARIES.items():
        p=ROOT/'work/arm-signal-tests/lib'/name
        rows.append({'component':name,'ready':p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest})
    print(json.dumps({'sdk_version':(ROOT/'sdk/VERSION').read_text().strip(),'checks':rows,'hardware_accessed':False},indent=2))
    return 0 if all(r['ready'] for r in rows) else 1

def bundle(ident,package,output):
    from verify_app_package import verify
    report=verify(package)
    if report['id']!=ident:raise ValueError('Wrong package')
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'dist') or output.exists():raise ValueError('Select a new dist ZIP output')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(package).rglob('*')):
            if p.is_symlink():raise ValueError('Linked package')
            if p.is_file():z.write(p,'HOMEBREW/apps/'+ident+'/'+p.relative_to(package).as_posix())
        z.writestr('HOMEBREW/data/'+ident+'/','')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    print(json.dumps({'archive':str(output.relative_to(ROOT)),'sha256':digest,'package':report,'installed':False},indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor');setup=sub.add_parser('setup');setup.add_argument('--stock-exe',type=Path)
    new=sub.add_parser('new');new.add_argument('id');new.add_argument('--template',choices=['minimal','touch-ui','canvas-game'],default='touch-ui');new.add_argument('--title')
    for command in ('build','preview','render','package'):
        s=sub.add_parser(command);s.add_argument('id');s.add_argument('--output',type=Path)
        if command in ('preview','render'):s.add_argument('--events',type=Path);s.add_argument('--data',action='store_true',help='Use isolated PC data under the preview output; never player storage')
        if command=='package':s.add_argument('--from-package',type=Path,required=True)
    args=p.parse_args()
    if args.command=='new':create(args.id,args.template,args.title);return 0
    if args.command=='doctor':return doctor()
    if args.command=='setup':
        from sdk_bootstrap import setup
        setup(args.stock_exe);return 0
    if args.id not in applications():p.error('Unknown app; create it with new or use build_app.py --list')
    definition=ROOT/'runtime/apps'/args.id
    if args.command=='package':
        version=(definition/'VERSION').read_text().strip();bundle(args.id,args.from_package,args.output or ROOT/'dist/sdk-apps'/(args.id+'-'+version+'.zip'));return 0
    output=args.output or ROOT/'work/sdk'/args.id/(args.command+'-'+str(time.time_ns()))
    if args.command=='build':
        from build_app import package
        from verify_app_package import verify
        output=fresh_work(output)
        compile_app(definition,output/'build')
        finished=package(args.id,output/'build',output/'package')
        print(json.dumps(verify(finished),indent=2));print(str(finished.relative_to(ROOT)));return 0
    # Both render and preview execute a host binary with the same app source.
    output=fresh_work(output);artifact=compile_app(definition,output/'host',host=True)
    command=[str(artifact),'--preview'] if args.command=='preview' else [str(artifact),'--render',str(output/'frame.ppm')]
    if args.events:
        if args.command!='render':p.error('--events is only accepted by render')
        command+=['--events',str(args.events.resolve())]
    if args.data:
        data=output/'data';data.mkdir();command+=['--data',str(data)]
    subprocess.run(command,cwd=definition,check=True)
    if args.command=='render':
        from PIL import Image
        with Image.open(output/'frame.ppm') as image:image.save(output/'frame.png')
        print(str((output/'frame.png').relative_to(ROOT)))
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        print('SDK: '+str(e),file=sys.stderr);sys.exit(1)
