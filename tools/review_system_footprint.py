"""PC-only rootfs footprint review; no deletion, remount, raw device or cleanup."""
from pathlib import Path
import argparse,datetime,hashlib,json
from terminal_client import connect,execute
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('host');parser.add_argument('--code-file',required=True)
args=parser.parse_args();code=Path(args.code_file).read_text(encoding='ascii').strip()
out=ROOT/'work/terminal-live'/datetime.datetime.now(datetime.timezone.utc).strftime('footprint-%Y%m%dT%H%M%SZ')
out.mkdir(parents=True,exist_ok=False)
queries={
 'root_summary':'df; cat /proc/mounts; ls -l /; du -kx /usr /lib /bin /sbin /etc; if [ -d /opt ]; then du -kx /opt; fi',
 'root_allocations':'du -akx /usr /lib /bin /sbin /etc',
 'stock_assets':'ls -l /usr/local; ls -l /usr/local/test; ls -l /usr/local/share; ls -l /usr/share; ls -l /lib/modules',
 'startup':'cat /etc/AppList.conf; cat /usr/local/bin/sysmgr.sh; cat /etc/init.d/icx1087driver; cat /etc/init.d/icx1087helper',
 'memory_processes':'''cat /proc/meminfo; for d in /proc/[0-9]*; do if [ -r "$d/status" ]; then echo "PROCESS $d"; grep -E '^(Name|Pid|PPid|VmSize|VmRSS|VmData|VmStk|Threads):' "$d/status"; ls -l "$d/exe" 2>/dev/null; fi; done''',
}
r={'scope':'Read-only directory/block allocation and startup/process observations, no delete/remount/driver or service changes.','results':{}}
for name,cmd in queries.items():
 try:
  with connect(args.host,2323,ROOT/'work/terminal-review/computer/server-cert.sha256',code) as s:data,status=execute(s,cmd,60)
  (out/(name+'.txt')).write_bytes(data)
  r['results'][name]={'command':cmd,'status':status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
  print(name,status,len(data),flush=True)
 except Exception as e:r['results'][name]={'command':cmd,'error':str(e)};print(name,str(e),flush=True)
 (out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
print(out)
