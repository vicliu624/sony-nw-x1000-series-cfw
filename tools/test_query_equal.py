"""Semantic query identity used by incremental job invalidation."""
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/query-equal';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/query_equal.c'];windows=os.name=='nt';out=w/('test.exe' if windows else 'test')
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True);subprocess.run([str(out)],check=True)
report=dict(passed=True,host='windows-clang' if windows else 'linux-gcc',sanitizers=not windows,device_accessed=False,checks=['padding and unused capacity ignored','active predicate/sort/parent changes distinguished','invalid graphs never equal'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/query_snapshot.h','tools/test_query_equal.py']})
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
