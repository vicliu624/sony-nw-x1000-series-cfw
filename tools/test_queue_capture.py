"""Queue plan transaction/cleanup checks with modeled owner methods."""
from pathlib import Path
import subprocess,json,hashlib,os
from app_registry import ROOT
w=ROOT/'work/queue-capture';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/queue_capture.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/queue_capture.c']
windows=os.name=='nt';output=w/('test-windows.exe' if windows else 'test')
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(output)],cwd=ROOT,check=True)
subprocess.run([str(output)],check=True)
report=dict(passed=True,host="windows-clang" if windows else "linux-gcc",sanitizers=not windows,device_accessed=False,checks=['acquire failure does not release unowned sequence','cache/query/validation failures release sequence','release failure prevents publication','successful pointer-free plan preserves unknown revision','invalid generation rejected before acquisition','group descriptor fallback preserves requested offset and limit','grouped shuffle refused atomically','caller workspace cannot alias output'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},limits=['Owner methods modeled; real cache extraction is tested separately. No qualified Met callback installed.'])
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
