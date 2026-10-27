"""Host unit tests for stock ABI bridge; legacy stat/realpath/abort are stubs."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-bridge-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/test_stock_fs_bridge.c']
subprocess.run(['gcc','-std=c99','-O2','-fno-builtin','-Wall','-Wextra','-Werror',*sources,'-o',str(work/'host-test')],cwd=ROOT,check=True)
cases=[('normal','16',0),('strcpy-fail','4',99),('snprintf-fail','4',99),('realpath-fail','16',99),('percent-n','16',99),('positional-n','16',99),('length-n','16',99),('bad-format','16',99),('unknown-format','16',99)]
rows=[]
for mode,size,expected in cases:
 p=subprocess.run([str(work/'host-test'),mode,size],cwd=work,capture_output=True,text=True,timeout=5)
 assert p.returncode==expected,(mode,p.returncode,p.stdout,p.stderr)
 rows.append({'case':mode,'exit':p.returncode})
for source in sources[:2]:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',source,'-o',str(work/(Path(source).stem+'.arm.o'))],cwd=ROOT,check=True)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources[:2]},'limits':['Old stat/realpath/abort are host stubs, not Sony libc; abort stub exits99 to avoid core files.','snprintf uses host vsnprintf; target varargs/libc behavior not yet qualified.','Fortified bridge is a conservative store profile: requires PATH_MAX4096 for nonnull realpath output; rejects %n and unknown/malformed format extensions.','ARM objects only; no linked target application, physical filesystem or Sony lifecycle verification.']}
(ROOT/'sources/native-stock-fs-bridge-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock ABI bridge:',len(rows),'host scenarios passed; ARM objects compiled.')
