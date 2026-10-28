"""Build and package one app using its local definition. PC only; no deployment."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from app_registry import ROOT,applications
from app_presentation import install_presentation
from market_metadata import parse_version

def package(ident,source,output):
    info=applications()[ident]
    if Path(source).is_symlink():raise ValueError('Linked package root')
    source=Path(source).resolve();output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work') or output==ROOT/'work' or output.exists():raise ValueError('Select a new project work directory')
    if source.is_symlink() or not source.is_dir():raise ValueError('Missing package input')
    files=list(source.rglob('*'))
    if any(p.is_symlink() for p in files):raise ValueError('Linked package input')
    version=(ROOT/'runtime/apps'/ident/'VERSION').read_text().strip();parse_version(version)
    if (source/'app.ini').is_file():
        manifest=dict(line.split('=',1) for line in (source/'app.ini').read_text().splitlines())
        if manifest.get('id')!=ident:raise ValueError('Package input belongs to another app')
    executable='app' if (source/'app.ini').is_file() else info.get('build',{}).get('executable','app')
    data=(source/executable).read_bytes()
    if len(data)<52 or data[:6]!=b'\x7fELF\x01\x01' or int.from_bytes(data[18:20],'little')!=40:raise ValueError('Expected little-endian ARM ELF')
    output.mkdir(parents=True)
    # A build directory may contain objects, logs or profiles: only package trees
    # are copied. Single-executable recipes must explicitly declare that mode.
    if info.get('build',{}).get('single_executable'):
        shutil.copyfile(source/executable,output/'app')
    else:
        shutil.copytree(source,output,dirs_exist_ok=True)
        if executable!='app':shutil.copyfile(source/executable,output/'app')
    for row in info.get('package_files',[]):
        origin=(ROOT/row['source']).resolve();dest=(output/row['destination']).resolve()
        if not origin.is_relative_to(ROOT) or not dest.is_relative_to(output) or Path(ROOT/row['source']).is_symlink():raise ValueError('Unsafe resource mapping')
        if not origin.is_file():raise ValueError('Missing required resource: '+str(origin))
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,dest)
    (output/'app.ini').write_text(f'api=1\nid={ident}\nname={info["title"]}\nversion={version}\ntarget={info["target"]}\nexec=app\nbytes={len(data)}\nsha256={hashlib.sha256(data).hexdigest()}\n')
    install_presentation(ident,output,version)
    (output/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.relative_to(output).as_posix()}\n' for p in sorted(output.rglob('*')) if p.is_file() and p.name!='files.sha256'))
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('id',nargs='?');parser.add_argument('--list',action='store_true');parser.add_argument('--output',type=Path);parser.add_argument('--build-output',type=Path,help='Fresh builder work directory, separate from package output');parser.add_argument('--package-from',type=Path,help='Package a freshly built app tree without invoking its builder');args,extra=parser.parse_known_args()
    apps=applications()
    if args.list:
        print('\n'.join(f'{ident}\t{info["title"]}' for ident,info in apps.items()));return
    if args.id not in apps:parser.error('Choose an ID from --list')
    info=apps[args.id];recipe=info.get('build',{});definition=ROOT/'runtime/apps'/args.id
    source=args.package_from
    if source is None:
        script=definition/recipe.get('script','build.py')
        if not script.is_file():parser.error('This app build has not yet been migrated; --package-from accepts a verified fresh package tree')
        builder_args=list(extra)
        if args.build_output:
            if not recipe.get('output_suffix') and recipe.get('output_suffix')!='':parser.error('This builder has no configurable output')
            builder_args+=['--output',str(args.build_output)]
        subprocess.run([sys.executable,str(script),*builder_args],cwd=ROOT,check=True)
        source=(args.build_output/recipe['output_suffix']) if args.build_output else ROOT/recipe['package']
    elif extra:parser.error('Unexpected packaging arguments')
    output=args.output or ROOT/'work/app-packages'/args.id/(definition/'VERSION').read_text().strip()
    result=package(args.id,source,output)
    inputs=[p for directory in ('runtime','tools') for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.c','.h','.S','.inc','.py','.json') and '__pycache__' not in p.parts]
    inputs += [ROOT/'VERSION',definition/'VERSION',*[p for p in (definition/'assets').rglob('*') if p.is_file()]]
    report={'id':args.id,'builder_invoked':args.package_from is None,'package':str(result.relative_to(ROOT)),'hardware_accessed':False,'firmware_created':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    result.with_name(result.name+'.build-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(result)
if __name__=='__main__':main()
