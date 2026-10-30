"""Real-thread host queue lifecycle; browser/native owner methods modeled."""
from pathlib import Path
import subprocess,json,hashlib
from app_registry import ROOT
w=ROOT/'work/player-host-queue';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/host_queue.c','tools/fixtures/player_host_queue.c']
subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',*sources,'-pthread','-o',str(w/'test')],cwd=ROOT,check=True)
subprocess.run([str(w/'test')],check=True,timeout=30)
report=dict(passed=True,device_accessed=False,checks=['no attach before observed Met callback','unrelated service thread arrives before music service','GUI attachment and matching-session-only Met capture','service-thread handoff and return using native-owner retirement','native owner bound/unbound only by Met','close waits for Met acknowledgement then reader drain','later callbacks cannot access closed browser'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/host_queue.h']},limits=['Browser and original native methods modeled. Native session-key extraction and R7 forwarding have separate ARM fixtures; physical runtime remains unqualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
