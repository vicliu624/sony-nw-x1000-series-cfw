"""Language preference writer fault checks, real PC files with device-ID fixtures."""
from pathlib import Path
import subprocess,tempfile,json,hashlib
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/language-storage-current-tests';w.mkdir(exist_ok=True)
sources=['tools/test_language_storage.c','runtime/apps/language/storage.c','runtime/apps/language/preference.c','runtime/apps/language/package.c','runtime/native/sha256.c'];out=w/'test'
subprocess.run(['gcc','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror',*sources,*['-Wl,--wrap='+s for s in ['fopen','open','lstat','fstat','write','fsync','rename']],'-o',str(out)],cwd=ROOT,check=True);folder=tempfile.mkdtemp(prefix='files-',dir=w);r=subprocess.run([str(out),folder],capture_output=True,text=True);assert r.returncode==0,r.stderr
report={'passed':True,'stdout':r.stdout,'scope':'Real PC files and directory descriptors; mount/device identity synthetic, no hardware','source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest()for s in sources+['tools/test_language_storage.py','runtime/apps/language/storage.h']}};(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(r.stdout)
