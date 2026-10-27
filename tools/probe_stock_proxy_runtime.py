"""PC-only full stock appproxy startup; no internal function or syscall hooks."""
from pathlib import Path
import hashlib,json,resource,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
tree=ROOT/'work/stock-manager-runtime-probe/root'
proxy=tree/'usr/local/bin/appproxy'
assert hashlib.sha256(proxy.read_bytes()).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
work=ROOT/'work/stock-proxy-runtime-probe';work.mkdir(exist_ok=False)
qemu=Path(shutil.which('qemu-arm-static'));bwrap=shutil.which('bwrap');assert bwrap
command=[bwrap,'--unshare-all','--die-with-parent','--new-session',
         '--ro-bind',str(tree),'/', '--dev','/dev','--proc','/proc',
         '--tmpfs','/tmp','--tmpfs','/var','--tmpfs','/run','--tmpfs','/contents',
         '--ro-bind',str(qemu),'/qemu','--chdir','/','--clearenv',
         '--setenv','PATH','/usr/local/bin:/usr/bin:/bin',
         '--','/qemu','-cpu','arm926','-strace','-0','appproxy',
         '/usr/local/bin/appproxy','/contents/HOMEBREW/launcher/app','--native']
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
tracked=[Path(__file__),proxy,qemu,work/'stdout.log',work/'stderr.log']
tracked.extend(p for p in (tree/'lib').iterdir() if p.is_file() and (p.name.startswith(('libc.','libpthread.','libresolv.','ld-'))))
report={'scope':'Unmodified stock appproxy startup without manager in PC-only isolated namespaces',
        'command':command,'exit':code,'timed_out':timed_out,'hardware_tested':False,
        'function_hooks':False,'manager_supplied':False,'stock_root_read_only':True,
        'source_hashes':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print('Stock appproxy probe:',code,'timeout:',timed_out)
print((work/'stderr.log').read_text(errors='replace')[-6500:])
