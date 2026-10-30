"""Prepare private PC/USB bootstrap pairing files. Never writes to a player."""
from pathlib import Path
import argparse,ipaddress,json,secrets,shutil,socket,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--list',action='store_true',help='List recent local thread IDs/titles on this computer only')
    p.add_argument('--thread',help='Codex thread UUID explicitly selected for this pet')
    p.add_argument('--address',help='This computer IPv4 address reachable from the player')
    p.add_argument('--title',default='Codex')
    p.add_argument('--port',type=int,default=4242)
    p.add_argument('--output',type=Path)
    p.add_argument('--codex-home',type=Path,default=Path.home()/'.codex')
    p.add_argument('--openssl',type=Path,default=Path('C:/Program Files/Git/usr/bin/openssl.exe') if sys.platform=='win32' else Path('/usr/bin/openssl'))
    a=p.parse_args()
    if a.list:
        index=a.codex_home/'session_index.jsonl';rows={}
        if index.is_file():
            for line in index.read_text(encoding='utf8').splitlines():
                try:row=json.loads(line)
                except ValueError:continue
                ident=row.get('id')
                if isinstance(ident,str):rows[ident]=row
        for ident,row in list(rows.items())[-20:]:print(ident+'\t'+str(row.get('thread_name',row.get('name','Codex'))).replace('\n',' ')[:96])
        return
    if not a.thread or not a.output:p.error('--thread and --output are required for pairing')
    if len(a.title.encode('utf8'))>96 or any(ord(c)<32 for c in a.title):p.error('Use a short single-line task title')
    address=ipaddress.IPv4Address(a.address or "0.0.0.0")
    if address.is_multicast or not 1<=a.port<=65535:p.error('Choose a reachable unicast IPv4 address and valid port')
    if len(a.thread)!=36 or any(c not in '0123456789abcdef-' for c in a.thread):p.error('Invalid selected thread UUID')
    matches=list((a.codex_home/'sessions').rglob('*'+a.thread+'.jsonl'))
    if len(matches)!=1:p.error('Selected active rollout not found exactly once')
    out=a.output.resolve()
    if not out.is_relative_to(ROOT/'work') or out==ROOT/'work' or out.exists():p.error('Use a fresh project work output directory')
    exe=Path(__file__).with_name('pet-bridge.exe')
    if not exe.is_file():exe=ROOT/'work/pet-bridge/windows/Release/pet-bridge.exe'
    if not exe.is_file():p.error('Build the native Windows bridge first')
    computer=out/'computer';computer.mkdir(parents=True)
    flags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
    def run(args):subprocess.run([str(x) for x in args],check=True,capture_output=True,creationflags=flags)
    run([a.openssl,'req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',computer/'key.pem','-out',computer/'cert.pem','-subj','/CN=X1000-Pet-Paired-Computer','-days','3650'])
    run([a.openssl,'x509','-in',computer/'cert.pem','-outform','DER','-out',computer/'cert.der'])
    run([a.openssl,'pkcs8','-topk8','-nocrypt','-in',computer/'key.pem','-outform','DER','-out',computer/'key.der'])
    token=secrets.token_bytes(32);cert=(computer/'cert.der').read_bytes()
    name=socket.gethostname().encode('utf8')[:63]
    while True:
        try:name.decode('utf8');break
        except UnicodeDecodeError:name=name[:-1]
    pair=b'PETPAIR1'+str(address).encode().ljust(16,b'\0')+struct.pack('>HH',a.port,len(cert))+token+name.ljust(64,b'\0')+cert
    if len(cert)>4096:raise ValueError('Oversized certificate')
    player=out/'PLAYER/HOMEBREW/data/pet';player.mkdir(parents=True);(player/'link.pair').write_bytes(pair)
    config={'listen':'0.0.0.0','discovery':True,'port':a.port,'token':token.hex(),'certificate':'cert.der','private_key':'key.der','rollout':str(matches[0]),'title':a.title}
    (computer/'computer.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    shutil.copyfile(exe,computer/'pet-bridge.exe')
    (computer/'Start Codex Pet.cmd').write_text('@echo off\ncd /d "%~dp0"\npet-bridge.exe computer.json\npause\n',encoding='ascii')
    licenses=computer/'LICENSES';licenses.mkdir();local=Path(__file__).parent/'LICENSES'
    shutil.copyfile(local/'JSON-MIT.txt' if local.is_dir() else ROOT/'third_party/pet-json/LICENSE.MIT',licenses/'JSON-MIT.txt')
    shutil.copyfile(local/'BearSSL-MIT.txt' if local.is_dir() else ROOT/'work/external-tls-probe/bearssl-0.6/LICENSE.txt',licenses/'BearSSL-MIT.txt')
    (out/'README.txt').write_text('Private pairing: do not publish this directory. Keep computer.json and its key files together. Copy PLAYER/HOMEBREW/data/pet/link.pair to visible player storage using the usual safe USB copy/eject procedure. Start computer/Start Codex Pet.cmd, keep this computer on the same reachable Wi-Fi, then open BSOD Pet. Menu header Codex opens connection controls; tap BSOD for task details. The bridge reads only the selected local Codex rollout. It cannot approve or execute Codex commands. If Windows prompts for network access, select only your trusted private network. No firewall rule, app-server setting or system service is changed by this tool.\n')
    print(json.dumps({'output':str(out.relative_to(ROOT)),'computer_endpoint':f'{address}:{a.port}','selected_thread':a.thread,'player_file':'PLAYER/HOMEBREW/data/pet/link.pair','device_written':False,'api_key_required':False}))
if __name__=='__main__':main()
