"""Offline release-host compatibility checks, no account or physical device."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/release-protocol-tests';w.mkdir(parents=True,exist_ok=True)
sources=['remote_catalog','download_plan','inventory','package','cleanup_plan','https_url','http_response','download_stream']
paths=['runtime/store/'+n+'.c' for n in sources]+['runtime/native/sha256.c','tools/test_release_protocol.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*paths,'-o',str(w/'test')],cwd=ROOT,check=True)
subprocess.run([str(w/'test')],check=True,timeout=15)
(w/'report.json').write_text(json.dumps({'passed':True,'checks':['HBSTORE2','HBSTORE1 hierarchical URL compatibility','injective flat asset names','unsafe URL/prefix/path rejection','authenticated redirect body excluded from payload','legacy redirect rejection retained','HTTP downgrade rejection'],'device_accessed':False},indent=2)+'\n')
