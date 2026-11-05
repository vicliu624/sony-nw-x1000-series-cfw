"""Build/review Core2 remote, without serial access or flashing."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
from app_registry import ROOT
project=ROOT/'runtime/apps/wireless-remote/core2';work=ROOT/'work/core2-remote-build'
work.mkdir(exist_ok=True);pio=Path.home()/'.platformio/penv/Scripts/pio.exe'
log=work/'build.log'
with log.open('w',encoding='utf-8') as output:
 result=subprocess.run([str(pio),'run','-d',str(project)],cwd=ROOT,
                       env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'),stdout=output,stderr=subprocess.STDOUT)
if result.returncode:raise RuntimeError(log.read_text(encoding='utf-8',errors='replace')[-5000:])
folder=work/'walkman-core2';artifacts={}
for name in ('firmware.bin','bootloader.bin','partitions.bin'):
 p=folder/name;data=p.read_bytes();artifacts[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
inputs=[p for p in project.rglob('*') if p.is_file() and '.pio' not in p.parts]
inputs += [ROOT/'runtime/apps/wireless-remote'/n for n in ('mode_wire.c','mode_wire.h','link.c','link.h','control.c','control.h','status_auth.c','status_auth.h','session_wire.c','session_wire.h','receiver.c','receiver.h','library_wire.c','library_wire.h','library_client.c','library_client.h')]
inputs += [ROOT/'runtime/native/sha256.c',ROOT/'runtime/native/sha256.h',Path(__file__)]
report=dict(built=True,version=(project/'VERSION').read_text().strip(),target='Core2 + Faces Gamepad3',
            artifacts=artifacts,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
            device_accessed=False,flashed=False,hardware_qualified=False,
            limitations=['Library protocol/UI integrated; actual native library/playlist/queue provider capabilities require physical acceptance','Five modes implemented but not physically accepted','Core2 display/touch/Gamepad unqualified'])
destination=ROOT/'work/core2-remote-reviews'/str(time.time_ns());destination.mkdir(parents=True)
for name,row in artifacts.items():
 target=destination/name;shutil.copy2(folder/name,target)
 if hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Core2 review artifact changed during snapshot')
 row['local']=target.relative_to(ROOT).as_posix()
(destination/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(built=True,version=report['version'],review=destination.relative_to(ROOT).as_posix(),artifacts=artifacts,flashed=False),indent=2))
