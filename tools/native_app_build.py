"""Shared original-libc compiler for app-local declarative build recipes."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(definition):
    definition=Path(definition).resolve();ident=definition.name
    recipe=json.loads((definition/'build.json').read_text());version=(definition/'VERSION').read_text().strip()
    work=ROOT/'work/app-builds'/ident;work.mkdir(parents=True,exist_ok=True);folder=work/'package';folder.mkdir(exist_ok=True)
    lib=ROOT/'work/arm-signal-tests/lib'
    for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
        if hashlib.sha256((lib/name).read_bytes()).hexdigest()!=digest:raise ValueError('Original library mismatch')
    sources=[]
    for name in recipe['sources']:
        path=(ROOT/name[2:] if name.startswith('@/') else definition/name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():raise ValueError('Invalid source: '+name)
        sources.append(path)
    flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_BUILD_VERSION="'+version+'"','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector',*recipe.get('cflags',[])]
    objects=[]
    for i,source in enumerate(sources):
        obj=work/(str(i)+'.o');source_flags=recipe.get('third_party_cflags',[]) if source.is_relative_to(ROOT/'third_party') else [];subprocess.run(['arm-linux-gnueabi-gcc',*flags,*source_flags,'-c',str(source),'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
    libraries=[str(ROOT/p) for p in recipe.get('libraries',[])]
    subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*objects,*libraries,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),*recipe.get('ldflags',[]),'-lgcc','-o',str(folder/'app')],cwd=ROOT,check=True)
    checks=[];env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD')
    for args in recipe.get('checks',[['--help']]):
        command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',':'.join([str(lib),*[str(ROOT/p) for p in recipe.get('library_paths',[])]]),str(folder/'app'),*args]
        run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=25)
        if run.returncode:raise RuntimeError((args,run.returncode,run.stdout,run.stderr))
        checks.append({'args':args,'stdout':run.stdout,'exit':0})
    report={'passed':True,'id':ident,'version':version,'checks':checks,'hardware_accessed':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources+[definition/'build.json',definition/'VERSION',definition/'build.py']}}
    (work/'build-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'id':ident,'passed':True,'bytes':(folder/'app').stat().st_size}))
