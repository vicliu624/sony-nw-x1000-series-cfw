"""Linux/WSL only: original-libc ARM TLS client against native C++ bridge."""
from pathlib import Path
import argparse,json,secrets,select,socket,struct,subprocess,time,hashlib
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--real-rollout',type=Path);parser.add_argument('--server',type=Path,default=ROOT/'work/pet-bridge/linux/build/pet-bridge');args=parser.parse_args()
work=ROOT/('work/pet-bridge/real-codex-test' if args.real_rollout else 'work/pet-bridge/arm-tls-test');work.mkdir(parents=True,exist_ok=True)
def run(args):subprocess.run([str(x) for x in args],check=True,capture_output=True)
run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',work/'key.pem','-out',work/'cert.pem','-subj','/CN=X1000-Pet-Native-Test','-days','1'])
run(['openssl','x509','-in',work/'cert.pem','-outform','DER','-out',work/'cert.der'])
run(['openssl','pkcs8','-topk8','-nocrypt','-in',work/'key.pem','-outform','DER','-out',work/'key.der'])
rollout=work/'selected.jsonl'
def event(value):
    with rollout.open('a',encoding='utf8') as f:f.write(json.dumps(value,ensure_ascii=False)+'\n')
if args.real_rollout:
    rollout=args.real_rollout.resolve()
    if not rollout.is_file():raise ValueError('Selected rollout missing')
else:
    rollout.write_text('');event({'type':'session_meta','payload':{'id':'native-arm-fixture'}});event({'type':'event_msg','payload':{'type':'task_started','turn_id':'one'}})
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
token=secrets.token_bytes(32);cert=(work/'cert.der').read_bytes()
pair=b'PETPAIR1'+b'127.0.0.1'.ljust(16,b'\0')+struct.pack('>HH',port,len(cert))+token+b'Paired PC'.ljust(64,b'\0')+cert
(work/'link.pair').write_bytes(pair)
config={'listen':'127.0.0.1','port':port,'token':token.hex(),'certificate':str(work/'cert.der'),'private_key':str(work/'key.der'),'rollout':str(rollout),'title':'中文任务'}
(work/'computer.json').write_text(json.dumps(config))
process=subprocess.Popen([str(args.server),str(work/'computer.json')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
lib=ROOT/'work/arm-signal-tests/lib'
probe=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(ROOT/'work/pet-bridge/linux/probe.arm'),str(work/'link.pair')]
try:
    time.sleep(1 if args.real_rollout else .2)
    for state in ([2] if args.real_rollout else [2,4]):
        if state==4:event({'type':'event_msg','payload':{'type':'task_complete','turn_id':'one','last_agent_message':'完成了'}})
        result=subprocess.run(probe+[str(state)],capture_output=True,text=True,timeout=12)
        if result.returncode:raise RuntimeError(str((result.returncode,result.stdout,result.stderr)))
        print(result.stdout.strip())
    if not args.real_rollout:
        event({'type':'event_msg','payload':{'type':'task_started','turn_id':'two'}})
        live=subprocess.Popen(probe+['2,4'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            assert select.select([live.stdout],[],[],10)[0]
            assert 'state 2' in live.stdout.readline()
            event({'type':'event_msg','payload':{'type':'task_complete','turn_id':'two','last_agent_message':'第二次完成'}})
            assert select.select([live.stdout],[],[],10)[0]
            assert 'state 4' in live.stdout.readline()
            assert live.wait(timeout=5)==0
        finally:
            if live.poll() is None:live.kill();live.wait()
        run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:prime256v1','-nodes','-keyout',work/'other-key.pem','-out',work/'other-cert.pem','-subj','/CN=Wrong-Peer','-days','1'])
        run(['openssl','x509','-in',work/'other-cert.pem','-outform','DER','-out',work/'other-cert.der'])
        other=(work/'other-cert.der').read_bytes()
        (work/'wrong.pair').write_bytes(pair[:26]+struct.pack('>H',len(other))+pair[28:124]+other)
        result=subprocess.run(probe[:-1]+[str(work/'wrong.pair'),'-1'],capture_output=True,text=True,timeout=12)
        assert result.returncode==0,(result.stdout,result.stderr)
        print('Persistent ARM session update and wrong-identity rejection passed')
    report={'passed':True,'client':'ARM926 + Sony original libc + native BearSSL','server':'native C++','source':'read-only actual selected Codex desktop rollout' if args.real_rollout else 'synthetic event fixture','checks':['pinned TLS handshake','pair token','request nonce','working state']+([] if args.real_rollout else ['persistent-session event update','wrong identity rejected']),'device_accessed':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'runtime/apps/pet').glob('link_*.c'))+list((ROOT/'runtime/apps/pet/computer').glob('*.cpp'))}}
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
