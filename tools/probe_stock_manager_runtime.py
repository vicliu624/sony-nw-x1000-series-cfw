"""Bounded PC-only launch of stock sysmgrd; no function hooks or device access."""
from pathlib import Path, PurePosixPath
import argparse,hashlib,json,os,resource,shutil,subprocess,tarfile

ROOT=Path(__file__).resolve().parents[1]
packed=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
work=ROOT/'work/stock-manager-runtime-probe'
work.mkdir(exist_ok=True)
tree=work/'root'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reuse-prepared',action='store_true')
options=parser.parse_args()
if options.reuse_prepared:
    previous=json.loads((work/'probe.json').read_text())
    for path in (packed,tree/'usr/local/bin/sysmgrd'):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==previous['source_hashes'][str(path.relative_to(ROOT))]
    for name in ('stdout.log','stderr.log','probe.json'):
        shutil.copyfile(work/name,work/('mount-failure-'+name))
else:
    assert not tree.exists(), 'Preserve previous probe; choose a fresh output before rerunning.'
    tree.mkdir()
# Materialize ordinary files only. Never create archive links on the host.
with tarfile.open(packed,'r:gz') as archive:
    for member in archive:
        name=PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        target=tree.joinpath(*name.parts)
        if options.reuse_prepared:continue
        if member.isdir():target.mkdir(parents=True,exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as output:shutil.copyfileobj(archive.extractfile(member),output)
            target.chmod(member.mode&0o777)
    # Stock library soname links become ordinary copies in this PC fixture.
    for member in archive.getmembers():
        if options.reuse_prepared:continue
        if not (member.issym() or member.islnk()):continue
        name=PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts
        try:source=archive.extractfile(member)
        except (KeyError,tarfile.ExtractError):continue
        if source is None:continue
        target=tree.joinpath(*name.parts);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output:shutil.copyfileobj(source,output)
        target.chmod(0o755)
for name in ('dev','proc','tmp','var','run','contents'): (tree/name).mkdir(exist_ok=True)
(tree/'qemu').touch(exist_ok=True)
qemu=Path(shutil.which('qemu-arm-static'))
bwrap=shutil.which('bwrap');assert bwrap
# No host root, drives, network or PID namespace are exposed to Sony processes.
command=[bwrap,'--unshare-all','--die-with-parent','--new-session',
         '--ro-bind',str(tree),'/', '--dev','/dev','--proc','/proc',
         '--tmpfs','/tmp','--tmpfs','/var','--tmpfs','/run','--tmpfs','/contents',
         '--ro-bind',str(qemu),'/qemu','--chdir','/','--clearenv',
         '--setenv','PATH','/usr/local/bin:/usr/bin:/bin',
         '--','/qemu','-cpu','arm926','-strace','/usr/local/bin/sysmgrd',
         '-r','/usr/local/bin/moc_repairer.sh','/etc/AppList.conf']
def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(8,8))
    resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
timed_out=False
with (work/'stdout.log').open('wb') as stdout,(work/'stderr.log').open('wb') as stderr:
    process=subprocess.Popen(command,stdout=stdout,stderr=stderr,preexec_fn=limits)
    try:code=process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        timed_out=True;process.kill();code=process.wait()
tracked=[Path(__file__),packed,qemu,tree/'usr/local/bin/sysmgrd',work/'stdout.log',work/'stderr.log']
report={'scope':'Unmodified stock sysmgrd in PC-only isolated filesystem/PID/network namespaces; not system emulation or hardware qualification',
        'command':command,'exit':code,'timed_out':timed_out,'hardware_tested':False,'firmware_created':False,
        'function_hooks':False,'stock_root_read_only':True,
        'source_hashes':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print('Stock sysmgrd probe:',code,'timeout:',timed_out)
print((work/'stderr.log').read_text(errors='replace')[-7000:])
