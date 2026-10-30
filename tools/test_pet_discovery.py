"""WSL loopback: real ARM discovery/TLS survives a peer IP/port change."""
from pathlib import Path
import hashlib,hmac,json,secrets,select,socket,struct,subprocess,time
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/pet-bridge/discovery-test';work.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run([str(x) for x in args],check=True,capture_output=True)
run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',work/'key.pem','-out',work/'cert.pem','-subj','/CN=Discovery-Peer','-days','1'])
run(['openssl','x509','-in',work/'cert.pem','-outform','DER','-out',work/'cert.der'])
run(['openssl','pkcs8','-topk8','-nocrypt','-in',work/'key.pem','-outform','DER','-out',work/'key.der'])
def free_port(kind):
    with socket.socket(socket.AF_INET,kind) as s:s.bind(('127.0.0.2',0));return s.getsockname()[1]
tcp=free_port(socket.SOCK_STREAM);udp=free_port(socket.SOCK_DGRAM);token=secrets.token_bytes(32);cert=(work/'cert.der').read_bytes()
rollout=work/'selected.jsonl';rollout.write_text(json.dumps({'type':'session_meta','payload':{'id':'discovery'}})+'\n'+json.dumps({'type':'event_msg','payload':{'type':'task_started','turn_id':'one'}})+'\n')
pair=b'PETPAIR1'+b'127.0.0.99'.ljust(16,b'\0')+struct.pack('>HH',1,len(cert))+token+b'Paired PC'.ljust(64,b'\0')+cert
(work/'link.pair').write_bytes(pair)
config={'listen':'127.0.0.254','port':tcp,'discovery':True,'discovery_port':udp,'token':token.hex(),'certificate':'cert.der','private_key':'key.der','rollout':str(rollout),'title':'Auto-discovery'}
server=ROOT/'work/pet-bridge/linux/gcc12-build/pet-bridge'
def start():
    (work/'computer.json').write_text(json.dumps(config));p=subprocess.Popen([str(server),str(work/'computer.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE);time.sleep(.15)
    if p.poll() is not None:raise RuntimeError(p.stderr.read().decode())
    return p
process=start();lib=ROOT/'work/arm-signal-tests/lib'
probe=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(ROOT/'work/pet-bridge/linux/probe.arm'),str(work/'link.pair'),'2,4',str(udp)]
client=None
try:
    # Unpaired request must not elicit a response.
    q=b'PTFIND01'+secrets.token_bytes(8);bad=q+hmac.new(bytes(32),q,hashlib.sha256).digest()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.settimeout(.25);s.sendto(bad,('127.0.0.254',udp))
        try:s.recv(256);raise AssertionError('Unpaired discovery reply')
        except socket.timeout:pass
    client=subprocess.Popen(probe,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    assert select.select([client.stdout],[],[],10)[0]
    first=client.stdout.readline();assert 'state 2' in first,first
    process.terminate();process.wait(timeout=5)
    config['listen']='127.0.0.253';config['port']=free_port(socket.SOCK_STREAM)
    with rollout.open('a') as f:f.write(json.dumps({'type':'event_msg','payload':{'type':'task_complete','turn_id':'one','last_agent_message':'Peer moved'}})+'\n')
    process=start()
    assert select.select([client.stdout],[],[],12)[0]
    second=client.stdout.readline();assert 'state 4' in second,second
    assert client.wait(timeout=3)==0
    assert (work/'link.pair').read_bytes()==pair
    report={'passed':True,'device_accessed':False,'client':'ARM926 + Sony libc','checks':['old saved IP and TCP port deliberately invalid','authenticated unicast LAN discovery','unpaired query ignored','automatic reconnection after peer IP and port change','no pairing-file rewrite','no firewall changes'],'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'runtime/apps/pet').glob('discovery*'))+list((ROOT/'runtime/apps/pet/computer').glob('discovery_server.*'))+[ROOT/'runtime/apps/pet/link_client.c']}}
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
    if client is not None and client.poll() is None:client.kill();client.wait()
    if process.poll() is None:process.terminate();process.wait(timeout=5)
