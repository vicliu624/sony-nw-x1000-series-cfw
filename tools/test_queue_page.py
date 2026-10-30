"""Offline queue assembler tests; native reader boundaries are modeled."""
from pathlib import Path
import subprocess,json,hashlib
from app_registry import ROOT
w=ROOT/'work/queue-page';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/queue_page.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/queue_page.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-g',*sources]
subprocess.run(['gcc',*common,'-fsanitize=address,undefined','-o',str(w/'test')],cwd=ROOT,check=True)
subprocess.run([str(w/'test')],cwd=ROOT,check=True)
for source in sources[:3]:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-c',str(ROOT/source),'-o',str(w/(Path(source).stem+'.o'))],check=True)
report=dict(passed=True,device_accessed=False,checks=['mixed cached IDs and shuffled uncached ordinals','atomic failure after first row','mask and ordinal bounds','overlap refusal','empty job and invalid request adoption'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},limits=['Reader calls are modeled. No live queue capture, publication, native database or hardware qualification.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
