"""Exercise ARM binary on ordinary temporary catalogs; no hardware mode invoked."""
from pathlib import Path
import json,hashlib,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=ROOT/'work/x1000-homebrew-frontend'
area=Path(tempfile.mkdtemp(prefix='native-files-',dir=ROOT/'work'));apps=area/'apps';apps.mkdir()
data=exe.read_bytes()
def install(id,name,crlf=False,root=None,payload=None):
    content=data if payload is None else payload
    p=(apps if root is None else root)/id;p.mkdir();(p/'app').write_bytes(content)
    fields={'api':'1','id':id,'name':name,'version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':str(len(content)),'sha256':hashlib.sha256(content).hexdigest()}
    text='\n'.join(k+'='+v for k,v in fields.items())+'\n'
    (p/'app.ini').write_bytes(text.replace('\n','\r\n').encode()if crlf else text.encode())
    return p
install('demo','DEMO FIXTURE');install('store','STORE FIXTURE',True);install('a'*32,'LONG ID FIXTURE')
(apps/'.install-unused').mkdir()
def invoke(mode,rc=0,root=None):
    run=subprocess.run(['qemu-arm','-cpu','arm926',str(exe),mode,str(apps if root is None else root)],capture_output=True,timeout=30)
    assert run.returncode==rc,(mode,run.returncode,run.stderr)
    return run.stdout
listing=invoke('--catalog').decode().splitlines();assert listing[0].startswith('store\t');assert len(listing)==3
checked=invoke('--check').decode();assert checked.count(' VERIFIED')==3
image=invoke('--render');assert len(image)==240*432*2
(area/'list.rgb565').write_bytes(image)
# Same file length and valid ELF header, changed payload: checksum must reject.
b=bytearray((apps/'demo/app').read_bytes());b[-1]^=1;(apps/'demo/app').write_bytes(b)
invoke('--check',3)
# Broken manifest cannot become a runnable item or a successful check.
f=apps/'demo/app.ini';f.write_bytes(f.read_bytes()+b'api=1\n')
invoke('--catalog',1)
# Correct size/hash and manifest must not make a Python script a native app.
script_apps=area/'script-apps';script_apps.mkdir()
script=b'#!/usr/bin/python\nprint(1)\n'+b'# padding\n'*10
install('script','SCRIPT FIXTURE',root=script_apps,payload=script)
assert invoke('--catalog',1,script_apps)==b''
invoke('--check',1,script_apps)
report={'scope':'qemu-user executes real ARM external binary; ordinary fixture files only','checks':['external discovery','store first','CRLF manifest','32-character ID','staging ignored','ARM SHA-256 file verification','render 240x432 RGB565','corruption rejected','invalid manifest reported','Python script with valid size/hash rejected as non-ELF'],'fixture_directory':str(area),'hardware_mode_invoked':False,'Sony_code_executed':False,'program_sha256':hashlib.sha256(data).hexdigest()}
(ROOT/'sources/native-files-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
