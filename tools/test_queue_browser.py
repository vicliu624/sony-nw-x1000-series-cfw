"""Threaded capture/exchange/async/page assembly integration, native boundaries modeled."""
from pathlib import Path
import subprocess,json,hashlib,os
from app_registry import ROOT
w=ROOT/'work/queue-browser';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/queue_browser.c','runtime/platform/player/queue_exchange.c','runtime/platform/player/queue_async.c','runtime/platform/player/group_reader.c','runtime/platform/player/group_native.c','runtime/platform/player/queue_page.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/queue_browser.c']
windows=os.name=='nt';output=w/('test-windows.exe' if windows else 'test')
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if windows:sources+=['tools/fixtures/windows_pthread.c']
else:flags+=['-fsanitize=address,undefined','-pthread']
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(output)],cwd=ROOT,check=True)
subprocess.run([str(output)],check=True,timeout=30)
report=dict(passed=True,host="windows-win32-shim" if windows else "linux-pthread",sanitizers=not windows,device_accessed=False,checks=['real capture and GUI worker threads','page requests through exchange and async reader','ordered metadata and partial last page','unknown revision refuses expected revision','revoke and externally quiesced close','balanced clients','flat to grouped plan transition','grouped offset across an empty group through async native steps'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},limits=['Native capture and Moma reads modeled. No real Met callback or public broker attachment enabled.'])
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
