"""Reproduce actual launcher grace with real cooperative HOST child processes.

An expected SIGKILL demonstrates a lifecycle incompatibility; no launcher code,
player, serial device or firmware is modified. Not a radio timing measurement.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-launcher-shutdown'
OUT.mkdir(parents=True,exist_ok=True)
fixture='tools/fixtures/xnow_shutdown_window.c'
runner_sources=[fixture,'runtime/native/app_process.c','runtime/native/linux_process_posix.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*runner_sources,'-o',str(OUT/'runner')],cwd=ROOT,check=True)
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DXNOW_SHUTDOWN_CHILD',fixture,'-o',str(OUT/'child')],cwd=ROOT,check=True)
rows=[]
for name,delay in (('short-cleanup',250),('long-cleanup',5000)):
    with tempfile.TemporaryDirectory(prefix=name+'-',dir=OUT) as temp:
        folder=Path(temp);shutil.copy2(OUT/'child',folder/'app')
        started=time.monotonic()
        run=subprocess.run([str(OUT/'runner'),str(folder),str(delay)],capture_output=True,text=True,timeout=10,check=True)
        duration=time.monotonic()-started
        match=re.fullmatch(r'wait_status=(\d+) stop=1\n',run.stdout);assert match,run.stdout
        status=int(match[1]);completed=(folder/'cleanup-complete').exists()
        assert (folder/'ready').exists()
        if name=='short-cleanup':assert status==0 and completed
        else:assert status==9 and not completed and duration<5
        rows.append({'case':name,'requested_cleanup_ms':delay,'elapsed_seconds':round(duration,3),
                     'wait_status':status,'cleanup_completed':completed,'cooperative_handler_installed':True})
report={'passed':True,'cases':rows,'scope':'actual launcher process function with host POSIX backend',
        'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in runner_sources},
        'long_cleanup_incompatibility_reproduced':True,'launcher_modified':False,
        'real_radio_restore_duration_measured':False,'device_accessed':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
