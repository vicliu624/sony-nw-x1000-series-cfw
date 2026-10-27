"""Mismatched launch/exit evidence must reject before producing a joined report."""
from pathlib import Path
import subprocess,sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];output=ROOT/'sources/invalid-provenance-should-not-exist.json';assert not output.exists();rows=[]
commands=[['tools/check_proxy_stop_order.py','--frontend-exit-report','sources/native-home-stop-frontend-contract.json','--registration-report','sources/native-manager-proxy-exec-request.json','--report',str(output.relative_to(ROOT))],['tools/check_proxy_manager_return.py','--proxy-exit-report','sources/native-home-stop-proxy-exit.json','--launch-report','sources/native-manager-proxy-exec-request.json','--report',str(output.relative_to(ROOT))]]
for command in commands:
 run=subprocess.run([sys.executable,*command],cwd=ROOT,capture_output=True,text=True,timeout=30)
 assert run.returncode!=0 and 'AssertionError' in run.stderr and not output.exists(),(command,run.returncode,run.stderr)
 rows.append({'tool':command[0],'mismatched_launch_rejected':True,'output_absent':True})
paths=['tools/check_proxy_stop_order.py','tools/check_proxy_manager_return.py','sources/native-home-stop-frontend-contract.json','sources/native-home-stop-proxy-exit.json','sources/native-manager-proxy-exec-request.json']
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'limits':['Host evidence provenance checks only; not kernel/IPC or hardware qualification.']}
(ROOT/'sources/native-return-provenance-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Mismatched launch evidence rejected by proxy and manager join tools; no output published.')
