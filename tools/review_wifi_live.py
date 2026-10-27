"""PC-side Wi-Fi observations only: no cnmgr requests or account actions."""
from pathlib import Path
import argparse,datetime,hashlib,json
from terminal_client import connect,execute
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('host');parser.add_argument('--code-file',required=True)
parser.add_argument('--dns-only',action='store_true')
args=parser.parse_args();code=Path(args.code_file).read_text(encoding='ascii').strip()
out=ROOT/'work/terminal-live'/datetime.datetime.now(datetime.timezone.utc).strftime('wifi-review-%Y%m%dT%H%M%SZ')
out.mkdir(parents=True,exist_ok=False)
queries={
 'network':'cat /proc/net/dev; cat /proc/net/route; cat /proc/net/wireless; readlink /etc/resolv.conf; cat /etc/resolv.conf; date; cat /proc/meminfo',
 'manager':'md5sum /usr/lib/libcnmgr.so.1.0 /usr/local/bin/cnmgr_daemon; cat /proc/mounts; /sbin/iptables -L INPUT -n; /sbin/iptables -L OUTPUT -n',
 'dns_probe':'ping -c 1 u.y.qq.com & probe=$!; sleep 3; kill -TERM "$probe" 2>/dev/null; wait "$probe"',
}
if args.dns_only:queries={'dns_probe':queries['dns_probe']}
r={'scope':'Read-only network/clock/library observations and one anonymous DNS/ICMP probe; no login, no new QR, no network reconfiguration, no device writes.','results':{}}
for name,cmd in queries.items():
 try:
  with connect(args.host,2323,ROOT/'work/terminal-review/computer/server-cert.sha256',code) as s:data,status=execute(s,cmd,12)
  (out/(name+'.txt')).write_bytes(data)
  r['results'][name]={'command':cmd,'status':status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
  print(name,status,len(data),flush=True)
 except Exception as e:r['results'][name]={'command':cmd,'error':str(e)};print(name,str(e),flush=True)
 (out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(out)
