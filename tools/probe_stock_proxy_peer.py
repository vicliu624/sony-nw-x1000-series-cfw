"""Launch unchanged Sony proxy with a PC C socket peer; not the real manager."""
from pathlib import Path
import argparse,hashlib,json,resource,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
tree=ROOT/'work/stock-manager-runtime-probe/root'
proxy=tree/'usr/local/bin/appproxy'
assert hashlib.sha256(proxy.read_bytes()).hexdigest()=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',default='work/stock-proxy-peer-probe')
options=parser.parse_args();work=(ROOT/options.output).resolve()
assert work.is_relative_to(ROOT/'work');work.mkdir(exist_ok=False)
source=ROOT/'tools/fixtures/stock_proxy_peer.c';peer=work/'peer'
subprocess.run(['gcc','-static','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(peer)],check=True)
for name in ('fixture','test-child'):(tree/name).touch(exist_ok=True)
qemu=Path(shutil.which('qemu-arm-static'));bwrap=shutil.which('bwrap');assert bwrap
command=[bwrap,'--unshare-all','--die-with-parent','--new-session',
 '--ro-bind',str(tree),'/', '--dev','/dev','--proc','/proc',
 '--tmpfs','/tmp','--tmpfs','/var','--tmpfs','/run','--tmpfs','/contents',
 '--ro-bind',str(qemu),'/qemu','--ro-bind',str(peer),'/fixture','--ro-bind',str(peer),'/test-child',
 '--chdir','/','--clearenv','--setenv','PATH','/usr/local/bin:/usr/bin:/bin','--','/fixture']
def limits():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(8,8));resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024*1024,4*1024*1024))
timed_out=False
with (work/'stdout.log').open('wb') as stdout,(work/'stderr.log').open('wb') as stderr:
 process=subprocess.Popen(command,stdout=stdout,stderr=stderr,preexec_fn=limits)
 try:code=process.wait(timeout=12)
 except subprocess.TimeoutExpired:timed_out=True;process.kill();code=process.wait()
tracked=[Path(__file__),source,peer,proxy,qemu,work/'stdout.log',work/'stderr.log']
report={'scope':'Real stock proxy with explicit C protocol peer and host test child, not Sony manager/ARM app/display qualification','exit':code,'timed_out':timed_out,'command':command,'function_hooks':False,'physical_device_access':False,'source_hashes':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
print((work/'stdout.log').read_text());print((work/'stderr.log').read_text(errors='replace')[-6500:])
