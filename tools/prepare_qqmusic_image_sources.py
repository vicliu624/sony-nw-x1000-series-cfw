"""Copy pinned official stb headers/license already acquired under work/."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'work/image-upstream/stb';dest=ROOT/'third_party/qqmusic-stb'
revision='003501f6d7a8668ce8b6d875e34dd97ad0d5d5b5'
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==revision
if dest.exists():raise FileExistsError('Review existing vendored image source explicitly')
dest.mkdir();files={}
for name in ('stb_image.h','stb_image_write.h','LICENSE'):
    shutil.copyfile(source/name,dest/name);files[name]=hashlib.sha256((dest/name).read_bytes()).hexdigest()
(ROOT/'sources/qqmusic-image-sources.json').write_text(json.dumps({'origin':'https://github.com/nothings/stb.git','revision':revision,'files':files,'license_choice':'MIT, retained LICENSE','changes':[]},indent=2)+'\n')
