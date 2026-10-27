"""PC-only, explicit read-only X1060 research snapshot over the paired terminal."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
from terminal_client import connect,execute

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('host')
parser.add_argument('--code-file',required=True)
parser.add_argument('--pin',default=str(ROOT/'work/terminal-review/computer/server-cert.sha256'))
args=parser.parse_args()
code=Path(args.code_file).read_text(encoding='ascii').strip()
out=ROOT/'work/terminal-live'/datetime.datetime.now(datetime.timezone.utc).strftime('snapshot-%Y%m%dT%H%M%SZ')
out.mkdir(parents=True,exist_ok=False)
queries={
 'system':'id; uname -a; cat /proc/cpuinfo; cat /proc/meminfo; cat /proc/mtd',
 'filesystems':'cat /proc/mounts; df; ls -l /dev/ptmx /dev/pts /dev/v4l /dev/sound /dev/fb',
 'drivers':'cat /proc/modules; cat /proc/devices',
 'firewall':'/sbin/iptables -L INPUT -n; /sbin/iptables -L OUTPUT -n',
 'permissions':'id; cat /proc/self/status',
}
report={'host':args.host,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Explicit read-only proc/device metadata/firewall listings. No file creation, system writes, raw device reads, mount/ioctl experiments or firmware changes on player.','queries':{}}
for name,command in queries.items():
    with connect(args.host,2323,args.pin,code) as sock:
        data,status=execute(sock,command,30)
    path=out/(name+'.txt');path.write_bytes(data)
    report['queries'][name]={'command':command,'status':status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    print(name,'status='+str(status),'bytes='+str(len(data)))
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Saved:',out)
