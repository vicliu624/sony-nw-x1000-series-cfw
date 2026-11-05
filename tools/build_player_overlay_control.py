"""Compile a hash-pinned one-start controller; no deployment or activation."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);a=p.parse_args()
review_path=(ROOT/Path(str(a.review).replace('\\','/'))).resolve()
if not review_path.is_relative_to(ROOT/'work'):raise ValueError('Private review must be under work/')
review=json.loads(review_path.read_text());files=review_path.parent/'files'
for source,digest in review['source_hashes'].items():
 if hashlib.sha256((ROOT/source).read_bytes()).hexdigest()!=digest:raise ValueError('Stale reviewed source: '+source)
for name,row in review['files'].items():
 if hashlib.sha256((files/name).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Stale reviewed file: '+name)
defines=['-DXW_LIVE_STAGE="'+review['device_directory']+'"']
for label,name in [('BASE','original/SpiderApp'),('PAYLOAD','sdk/SpiderApp'),('LIBRARY','sdk/libx1000-player.so'),('WRAPPER','wrapper/SpiderApp')]:
 row=review['files'][name];defines+=['-DXW_LIVE_'+label+'_SHA="'+row['sha256']+'"','-DXW_LIVE_'+label+'_BYTES='+str(row['bytes'])+'UL']
out=ROOT/'work/player-overlay-control'/str(time.time_ns());out.mkdir(parents=True);artifact=out/'player-overlay-control.arm';libs=stock_libraries()
sources=['runtime/platform/player/volatile_overlay.c','runtime/native/sha256.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-no-pie','-fno-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none',*defines,*sources,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(artifact),'--help'],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=10);assert run.returncode==0
report=dict(artifact=str(artifact.relative_to(ROOT)),bytes=artifact.stat().st_size,sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),review=str(review_path.relative_to(ROOT)),help_original_libc_arm=True,device_accessed=False,activated=False,source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources})
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
