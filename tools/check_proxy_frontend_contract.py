"""Regenerate original proxy argv, then consume it in the ARM frontend adapter.

Separate virtual address spaces joined at captured exec arguments. Not OS process
emulation, Sony return qualification, firmware boot or physical-device execution.
"""
from pathlib import Path
import subprocess
import sys
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,'tools/check_applist_fragment.py','--full-config'],cwd=ROOT,check=True,timeout=60)
for option in ('--capture-frontend-exec','--no-launch-arguments'):
    subprocess.run([sys.executable,'tools/check_manager_change_notification.py',option],cwd=ROOT,check=True,timeout=60)
subprocess.run([sys.executable,'tools/test_native_adapter.py',
    '--proxy-exec-report','sources/native-manager-proxy-exec-request.json',
    '--proxy-exec-report','sources/native-manager-proxy-noargs-exec.json'],cwd=ROOT,check=True,timeout=60)
subprocess.run([sys.executable,'tools/check_proxy_exec_failure.py'],cwd=ROOT,check=True,timeout=60)
subprocess.run([sys.executable,'tools/check_proxy_stop_order.py',
    '--frontend-exit-report','sources/native-proxy-frontend-contract.json',
    '--exec-failure-report','sources/native-proxy-exec-failure.json'],cwd=ROOT,check=True,timeout=60)
subprocess.run([sys.executable,'tools/check_home_parent.py','--native-frame-receiver'],cwd=ROOT,check=True,timeout=120)
subprocess.run([sys.executable,'tools/check_proxy_manager_return.py','--home-confirmation-report',
    'sources/native-home-parent-frame-receiver.json'],cwd=ROOT,check=True,timeout=60)
subprocess.run([sys.executable,'tools/check_proxy_manager_return.py','--native-registry'],cwd=ROOT,check=True,timeout=60)
reports={}
for name in ('native-applist-full-config.json','native-proxy-frontend-contract.json','native-proxy-exec-failure.json','native-frontend-proxy-exit.json','native-proxy-manager-return.json','native-proxy-manager-responder-native-registry.json','native-home-parent-frame-receiver.json'):
    content=(ROOT/'sources'/name).read_bytes()
    reports[name]={'sha256':hashlib.sha256(content).hexdigest(),'evidence':json.loads(content)}
summary={'scope':'Original launch argv -> ARM frontend -> captured exit -> original proxy reap/self-event shutdown -> manager process reaper/return; virtual IPC/devices/processes between address spaces, no inserted managerop3',
         'reports':reports,'all_passed':True,'physical_device_access':False,'Sony_return_validated':False,'proxy_self_event_shutdown_not_manager_op3':True,
         'remaining':'Proxy shutdown targets its native own event port, no managerop3 inserted. Proxy process exit feeds manager reaper/return; real kernel IPC/wait/scheduling, launch services and hardware restoration remain supplied. Startup state1 is a fixture.'}
(ROOT/'sources/native-entry-exit-contract.json').write_text(json.dumps(summary,indent=2)+'\n')
