"""Host-only persistent installation metadata checks; never contacts QQ."""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-installation-tests';work.mkdir(parents=True,exist_ok=True)
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-g','runtime/apps/qqmusic/qqmusic_installation.c','tools/test_qqmusic_installation.c','-o',str(work/'test')],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as folder:subprocess.run([str(work/'test'),folder],check=True,timeout=10)
