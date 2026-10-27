"""Offline interaction controller checks, with a simulated installer callback."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/store-session-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/session.c','tools/test_store_session.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'test')],cwd=ROOT,check=True)
subprocess.run([str(work/'test')],check=True)
local_sources=['runtime/store/session.c','runtime/store/session_local.c','tools/test_store_session_local.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*local_sources,'-o',str(work/'local-test')],cwd=ROOT,check=True)
subprocess.run([str(work/'local-test')],check=True)
sources+=['runtime/store/session_local.c','tools/test_store_session_local.c']
view_sources=['runtime/store/session.c','runtime/store/view.c','tools/test_store_view.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*view_sources,'-o',str(work/'view-test')],cwd=ROOT,check=True)
subprocess.run([str(work/'view-test')],check=True)
sources+=['runtime/store/view.c','tools/test_store_view.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-c','runtime/store/session.c','-o',str(work/'session.arm.o')],cwd=ROOT,check=True)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'backend':'simulated callback','checks':['No operation on initialize/request/back','Explicit confirmation invokes one action','Running session rejects reentry','All installer result codes retained','Recovery/cleanup blocks new install even after Back','Confirmed recovery allows retry after success','Idle cancellation requires confirmation','Unknown result conservatively requires recovery'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['No rendering, input, USB handoff or real installer binding.','Synchronous callback, not background UI or cancellation delivery.','ARM object compiled only; no device execution or candidate integration.']}
(ROOT/'sources/native-store-session-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Store interaction controller checks passed; backend simulated.')
