"""Offline local-package pagination and selection checks."""
from pathlib import Path
import subprocess,hashlib,json
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-catalog-view-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/session.c','runtime/store/view.c','runtime/store/canvas.c','runtime/store/catalog_view.c','runtime/store/catalog_loop.c','runtime/native/frontend.c','tools/test_store_catalog_view.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'test')],cwd=ROOT,check=True)
subprocess.run([str(work/'test')],check=True)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'checks':['Empty catalog cannot select','32 items across six pages','Last-page empty rows cannot select','Next/previous/exit/out-of-bounds','Invalid count rejected'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Host synthetic catalog, not directory scanner boundary coverage.','Memory canvas; no physical display or input.']}
(ROOT/'sources/native-store-catalog-view-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Local catalog view pagination/selection checks passed.')
