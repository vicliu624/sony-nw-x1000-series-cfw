"""Offline touch/present/store loop with simulated platform and backend."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/store-ui-loop-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/session.c','runtime/store/view.c','runtime/store/canvas.c','runtime/store/ui_loop.c','runtime/native/frontend.c','tools/test_store_ui_loop.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'test')],cwd=ROOT,check=True)
subprocess.run([str(work/'test')],check=True)
for source in sources[:-1]:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-c',source,'-o',str(work/(Path(source).stem+'.arm.o'))],cwd=ROOT,check=True)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'checks':['Original 11-byte touch decoder','Drag ignored','Working presented before backend','Return and exit','Failed presentation invokes no backend'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Host scripted platform/backend, not hardware qualification.','ARM object compilation only, not ARM loop execution.','Synchronous I/O: USB handoff and runtime cancellation unimplemented.']}
(ROOT/'sources/native-store-ui-loop-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Store UI loop checks passed; platform/backend simulated.')
