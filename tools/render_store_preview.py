"""Render C RGB565 store pages to PPM; no device or Python runtime payload."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-preview';work.mkdir(exist_ok=True)
sources=['runtime/store/session.c','runtime/store/view.c','runtime/store/canvas.c','tools/render_store_preview.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'render')],cwd=ROOT,check=True)
subprocess.run([str(work/'render'),str(work)],check=True)
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-c','runtime/store/canvas.c','-o',str(work/'canvas.arm.o')],cwd=ROOT,check=True)
report={'physical_device_access':False,'canvas_guard_checks_passed':True,'format':'240x432 RGB565 rendered as PPM','pages':{name:hashlib.sha256((work/(name+'.ppm')).read_bytes()).hexdigest() for name in ('list','confirm','working','complete','recovery')},'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Host-rendered fixture states with simulated backend, not hardware display/touch qualification.','Native font only; no Unicode font implementation.','No framebuffer present or USB integration.']}
(ROOT/'sources/native-store-preview.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five C canvas previews and guards passed; ARM canvas object compiled.')
