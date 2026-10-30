"""ARM compiler frame budget for player paths; not a whole-program stack proof."""
from pathlib import Path
import hashlib,json,subprocess
from app_registry import ROOT
w=ROOT/'work/player-stack-check';w.mkdir(exist_ok=True)
rows=[];sources=[]
for name in ('client','rpc_posix','rpc_wire','player_broker'):
 source='runtime/platform/player/'+name+'.c';sources.append(source)
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fstack-usage','-Wframe-larger-than=2048','-Werror','-c',source,'-o',str(w/(name+'.o'))],cwd=ROOT,check=True)
 for row in (w/(name+'.su')).read_text().splitlines():
  location,size,kind=row.split('\t');assert int(size)<=2048,(location,size)
  rows.append(dict(function=location.rsplit(':',1)[1],bytes=int(size),kind=kind))
report=dict(passed=True,arm_compiler_frames=True,maximum_local_frame=max(r['bytes'] for r in rows),frames=rows,device_accessed=False,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_player_stack.py']},limits=['This bounds compiler-local frames in the selected sources, not total call depth or original Sony/library stack use.','Caller-owned contexts are larger; keep them in static/heap storage, not small thread stacks.','The native database worker page staging has its own larger frame and is intentionally excluded from GUI/client frame claims.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
