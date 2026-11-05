"""Build the original Cardputer LCD front end; never opens serial or flashes."""
import hashlib,json,os,re,shutil,struct,subprocess,sys
from pathlib import Path
from app_registry import ROOT
project=ROOT/'runtime/apps/wireless-remote/cardputer'
dependency=ROOT/'work/cardputer-remote-deps/M5GFX'
cached=ROOT/'work/espnow-chat-cardputer-libdeps/cardputer-chat/M5GFX'
if not dependency.exists():
    if not cached.is_dir():raise RuntimeError('Prepare the M5Stack M5GFX0.2.35 source component before this build')
    shutil.copytree(cached,dependency,ignore=shutil.ignore_patterns('.git','__pycache__'))
if json.loads((dependency/'library.json').read_text(encoding='utf-8'))['version']!='0.2.35':raise ValueError('Pinned M5GFX0.2.35 required')
pio=Path.home()/'.platformio/penv/Scripts/pio.exe'
if not pio.is_file():pio=Path.home()/'.platformio/penv/bin/pio'
config=ROOT/'work/cardputer-remote-build/sdkconfig'
if config.exists():
    text=config.read_text(encoding='utf-8')
    updates={'PARTITION_TABLE_SINGLE_APP':'# CONFIG_PARTITION_TABLE_SINGLE_APP is not set','PARTITION_TABLE_CUSTOM':'CONFIG_PARTITION_TABLE_CUSTOM=y','PARTITION_TABLE_FILENAME':'CONFIG_PARTITION_TABLE_FILENAME="partitions.csv"'}
    for key,value in updates.items():
        text=re.sub(r'^(?:# )?CONFIG_'+key+r'(?:=.*| is not set)$',value,text,flags=re.MULTILINE)
    if text!=config.read_text(encoding='utf-8'):config.write_text(text,encoding='utf-8')
environment=dict(os.environ,X1000_M5GFX_COMPONENT=str(dependency),X1000_REMOTE_SDKCONFIG_PATH=config.as_posix(),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
log=ROOT/'work/cardputer-remote-build/build.log';log.parent.mkdir(parents=True,exist_ok=True)
with log.open('w',encoding='utf-8') as output:
    result=subprocess.run([str(pio),'run','-d',str(project)],cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT)
if result.returncode:raise RuntimeError(log.read_text(encoding='utf-8',errors='replace')[-6000:])
if 'CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192' not in config.read_text(encoding='utf-8'):raise ValueError('Expected8KiB main stack configuration')
artifact=ROOT/'work/cardputer-remote-build/walkman-remote/firmware.bin'
partition_table=(artifact.parent/'partitions.bin').read_bytes();app_partition_bytes=None
for offset in range(0,len(partition_table),32):
    magic,kind,sub,start,size,name,flags=struct.unpack_from('<HBBII16sI',partition_table,offset)
    if magic!=0x50aa:break
    if start+size>8388608:raise ValueError('Partition exceeds8MB flash')
    if kind==0 and start==0x10000:app_partition_bytes=size
if app_partition_bytes!=0x300000 or artifact.stat().st_size>app_partition_bytes:raise ValueError('Firmware must fit the explicit3MiB factory partition')
shared=[ROOT/p for p in ('runtime/apps/wireless-remote/link.c','runtime/apps/wireless-remote/link.h','runtime/apps/wireless-remote/session_wire.c','runtime/apps/wireless-remote/session_wire.h','runtime/apps/wireless-remote/receiver.c','runtime/apps/wireless-remote/receiver.h','runtime/apps/wireless-remote/control.c','runtime/apps/wireless-remote/control.h','runtime/platform/player/player.h','runtime/platform/player/provider.h','runtime/apps/wireless-remote/status_auth.c','runtime/apps/wireless-remote/status_auth.h','runtime/native/sha256.c','runtime/native/sha256.h')]
tracked=[p for p in project.rglob('*') if p.is_file() and not p.name.startswith('sdkconfig.walkman')]+shared+[ROOT/'tools/build_cardputer_remote.py']
report=dict(built=True,artifact=str(artifact.relative_to(ROOT)),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),version=(project/'VERSION').read_text().strip(),lcd_frontend=True,status_receiver_implemented=True,main_stack_bytes=8192,player_link_implemented=False,serial_opened=False,flashed=False,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},dependency_version='0.2.35',dependency_hashes={str(p.relative_to(dependency)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependency.rglob('*') if p.is_file()},limits=['Authenticated status receiver and renderer implemented; Keyboard commands and receipts implemented; original-player lifecycle and RF integration remain unqualified.','No device acceptance, physical link or screen visibility is implied by compilation.'])
out=ROOT/'work/cardputer-remote-build/build-report.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='dependency_hashes'},indent=2))
