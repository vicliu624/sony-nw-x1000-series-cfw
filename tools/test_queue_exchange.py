"""Offline pointer-free Met/GUI queue exchange checks."""
from pathlib import Path
import subprocess,json,hashlib
from app_registry import ROOT
w=ROOT/'work/queue-exchange';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/queue_exchange.c','tools/fixtures/queue_exchange.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',*sources,'-pthread','-o',str(w/'test')],cwd=ROOT,check=True)
subprocess.run([str(w/'test')],check=True)
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-c',str(ROOT/sources[0]),'-o',str(w/'queue_exchange.o')],check=True)
report=dict(passed=True,device_accessed=False,checks=['superseded capture refused','atomic read and error propagation','revoked capture refused','GUI affinity','generation exhaustion refuses wrap'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},limits=['No Met callback installed; concurrent capture and original runtime remain unqualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
