"""PC-only loopback integration test of the native paired TLS endpoint."""
from pathlib import Path
import argparse,hashlib,hmac,json,os,secrets,socket,ssl,struct,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--real-rollout',type=Path);options=parser.parse_args()
WORK=ROOT/('work/pet-bridge/windows-real-test' if options.real_rollout else 'work/pet-bridge/tls-test');WORK.mkdir(parents=True,exist_ok=True)
EXE=ROOT/'work/pet-bridge/windows/Release/pet-bridge.exe'
OPENSSL=Path('C:/Program Files/Git/usr/bin/openssl.exe')
flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
def run(args):subprocess.run([str(x) for x in args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
run([OPENSSL,'req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',WORK/'key.pem','-out',WORK/'cert.pem','-subj','/CN=X1000-Pet-Local-Test','-days','1'])
run([OPENSSL,'x509','-in',WORK/'cert.pem','-outform','DER','-out',WORK/'cert.der'])
run([OPENSSL,'pkcs8','-topk8','-nocrypt','-in',WORK/'key.pem','-outform','DER','-out',WORK/'key.der'])
rollout=WORK/'selected.jsonl'
def event(value):
    with rollout.open('a',encoding='utf8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
if options.real_rollout:rollout=options.real_rollout.resolve()
else:
    rollout.write_text('',encoding='utf8')
    event({'type':'session_meta','payload':{'id':'selected-tls-fixture'}})
    event({'type':'event_msg','payload':{'type':'task_started','turn_id':'turn1'}})
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
token=secrets.token_bytes(32);pin=hashlib.sha256((WORK/'cert.der').read_bytes()).digest()
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('127.0.0.1',0));discovery_port=s.getsockname()[1]
config={'listen':'127.0.0.1','port':port,'token':token.hex(),'certificate':str(WORK/'cert.der'),'private_key':str(WORK/'key.der'),'rollout':str(rollout),'title':'中文任务'}
config.update(discovery=True,discovery_port=discovery_port)
(WORK/'computer.json').write_text(json.dumps(config),encoding='utf8')
process=subprocess.Popen([str(EXE),str(WORK/'computer.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
def exact(s,n):
    b=b''
    while len(b)<n:
        chunk=s.recv(n-len(b))
        if not chunk:raise EOFError('Truncated response')
        b+=chunk
    return b
def snapshot(secret=token,expected_pin=pin):
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
    with context.wrap_socket(socket.create_connection(('127.0.0.1',port),timeout=4),server_hostname='paired-peer') as s:
        # Exact certificate pin is the trust root for this private pairing.
        if hashlib.sha256(s.getpeercert(binary_form=True)).digest()!=expected_pin:raise ValueError('Pin mismatch before authentication')
        nonce=secrets.randbits(64);s.sendall(b'PET1'+secret+struct.pack('>Q',nonce))
        n=struct.unpack('>H',exact(s,2))[0];assert 36<=n<=2048
        frame=exact(s,n);assert frame[:8]==b'PTSNAP01' and struct.unpack('>Q',frame[8:16])[0]==nonce
        return frame
try:
    for attempt in range(40):
        try:first=snapshot();break
        except (OSError,EOFError):
            if process.poll() is not None:raise RuntimeError(process.stderr.read().decode())
            time.sleep(.05)
    else:raise AssertionError('Server not ready')
    assert first[24]==2
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.settimeout(1);nonce=secrets.token_bytes(8);query=b'PTFIND01'+nonce;s.sendto(query+hmac.new(token,query,hashlib.sha256).digest(),('127.0.0.1',discovery_port));reply,_=s.recvfrom(128)
        assert len(reply)==82 and reply[:8]==b'PTHERE01' and reply[8:16]==nonce and reply[18:50]==pin and struct.unpack('>H',reply[16:18])[0]==port and hmac.compare_digest(reply[50:],hmac.new(token,reply[:50],hashlib.sha256).digest())
    if not options.real_rollout:
        event({'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn1','last_agent_message':'已经完成'}})
        assert snapshot()[24]==4
    try:snapshot(secret=bytes(32));raise AssertionError('Wrong token accepted')
    except (EOFError,OSError):pass
    try:snapshot(expected_pin=bytes(32));raise AssertionError('Wrong certificate accepted')
    except ValueError:pass
    report={'passed':True,'native_server':True,'source':'actual selected Windows Codex rollout' if options.real_rollout else 'synthetic fixture','tls':'1.2 exact certificate pin','checks':['paired working snapshot','authenticated UDP discovery response','wrong token rejected','wrong pin rejected before token','nonce bound response','Chinese metadata']+([] if options.real_rollout else ['newly appended completion event']),'device_accessed':False}
    (WORK/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
