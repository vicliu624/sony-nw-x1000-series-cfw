"""ARM BearSSL transactions against local Python TLS fixtures, never remote QQ."""
from pathlib import Path
import hashlib
import json
import os
import sys
import re
import socket
import ssl
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
work = ROOT/'work/qqmusic-tls'
work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib = ROOT/'work/arm-signal-tests/lib'
crypto = ROOT/'work/external-tls-probe'
rt = ROOT/'work/stock-resolver-probe/librt.so.1'
for name, digest in {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    assert hashlib.sha256((lib/name).read_bytes()).hexdigest() == digest
sources = ['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('session','protocol','cookie','http','response','tls','json','credential','cgi','resource')]
sources += ['runtime/store/'+n+'.c' for n in ('stock_tls_compat','socket_step','tls_socket_step','deadline')]
sources += ['tools/fixtures/qqmusic_tls.c','runtime/store/start.c','runtime/store/start.S']
sources += ['runtime/native/sha256.c']
sources += ['runtime/store/https_url.c']
app = work/'tls-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                '-DHB_STORE_LIBC_CLOCK','-march=armv5te','-marm','-mfloat-abi=soft',
                '-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie',
                '-Wl,--hash-style=sysv','-Wl,--build-id=none',
                '-Wl,--dynamic-linker=/lib/ld-linux.so.3',
                '-Wl,-rpath-link,'+str(rt.parent),
                '-I'+str(crypto/'bearssl-0.6/inc'),*sources,
                str(crypto/'arm-build/libbearssl.a'),str(rt),str(lib/'libc.so.6'),
                str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)

rows=[]
with tempfile.TemporaryDirectory(prefix='local-certs-',dir=work) as temporary:
    tmp=Path(temporary)
    # Test-only self-signed CA/leaf, never installed or packaged as app trust.
    for name,host in [('good','graph.qq.com'),('wrong','localhost')]:
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                        '-keyout',str(tmp/(name+'.key')),'-out',str(tmp/(name+'.pem')),
                        '-days','1','-subj','/CN='+host,'-addext','subjectAltName=DNS:'+host+(',DNS:u.y.qq.com,DNS:isure.stream.qqmusic.qq.com' if name=='good' else ''),
                        '-addext','basicConstraints=critical,CA:TRUE'],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['openssl','x509','-in',str(tmp/(name+'.pem')),'-outform','DER',
                        '-out',str(tmp/(name+'.der'))],check=True)
    cases=['fixed','chunked','close','truncated','raw-eof','untrusted','hostname','expired','cancel','deadline','late-cancel','stall-close','cgi-login','cgi-device-limit','media-stream','media-raw-eof','cgi-eof','cgi-chunk-eof','cgi-truncated-eof','media-truncated-eof','raw-close-eof']
    if '--cgi-framed' in sys.argv:cases=['raw-eof','media-raw-eof','cgi-eof','cgi-chunk-eof','cgi-truncated-eof']
    if '--framed-http' in sys.argv:cases=['raw-eof','media-raw-eof','cgi-eof','cgi-chunk-eof','cgi-truncated-eof','media-truncated-eof','raw-close-eof']
    for case in cases:
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(8)
        port=listener.getsockname()[1];server_errors=[];observed=[]
        def serve():
            tls=None
            try:
                peer,_=listener.accept();peer.settimeout(8)
                context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
                cert='wrong' if case=='hostname' else 'good'
                context.load_cert_chain(tmp/(cert+'.pem'),tmp/(cert+'.key'))
                tls=context.wrap_socket(peer,server_side=True)
                data=b''
                while b'\r\n\r\n' not in data:
                    part=tls.recv(4096)
                    if not part: return
                    data+=part
                    if len(data)>8192: raise ValueError('oversized request')
                headers,body=data.split(b'\r\n\r\n',1)
                length=int(next((v.split(b':',1)[1] for v in headers.split(b'\r\n') if v.lower().startswith(b'content-length:')),b'0'))
                while len(body)<length:
                    part=tls.recv(4096)
                    if not part: return
                    body+=part
                if case.startswith('media-'):
                    assert headers.startswith(b'GET /M800MEDIA02.mp3?vkey=synthetic HTTP/1.1\r\nHost: isure.stream.qqmusic.qq.com\r\n')
                    assert b'cookie:' not in headers.lower() and not body
                elif case.startswith('cgi-'):
                    assert headers.startswith(b'POST /cgi-bin/musicu.fcg HTTP/1.1\r\nHost: u.y.qq.com\r\n')
                    payload=json.loads(body)
                    assert payload['req_0']=={'module':'QQConnectLogin.LoginServer','method':'QQLogin','param':{'code':'synthetic_code'}}
                    assert payload['comm']['tmeLoginType']=='2'
                    assert b'Content-Type: application/json' in headers
                else:
                    assert headers.startswith(b'POST /oauth2.0/authorize HTTP/1.1\r\nHost: graph.qq.com\r\n')
                    assert b'state=random-state' in body
                assert len(body)==length
                observed.append(True)
                if case=='deadline': time.sleep(.15)
                base=b'HTTP/1.1 200 OK\r\nSet-Cookie: test=synthetic; Secure\r\n'
                if case.startswith('media-'):
                    data=bytes(i%251 for i in range(3*1024*1024+17))
                    response=base+b'Content-Type: application/octet-stream\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+(data[:-1] if case=='media-truncated-eof' else data)
                elif case.startswith('cgi-'):
                    result={'code':0,'req_0':{'code':20279,'data':{}}} if case=='cgi-device-limit' else {'code':0,'req_0':{'code':0,'data':{'musicid':9007199254740993,'musickey':'synthetic_key','loginType':2}}}
                    data=json.dumps(result,separators=(',',':')).encode()
                    response=base+b'Content-Type: application/json\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+(data[:-1] if case=='cgi-truncated-eof' else data)
                    if case=='cgi-chunk-eof':response=base+b'Transfer-Encoding: chunked\r\n\r\n'+('%x\r\n'%len(data)).encode()+data+b'\r\n0\r\n\r\n'
                elif case=='chunked': response=base+b'Transfer-Encoding: chunked\r\n\r\n2\r\nhe\r\n3\r\nllo\r\n0\r\n\r\n'
                elif case in ('close','raw-close-eof'): response=base+b'\r\nhello'
                else: response=base+b'Content-Length: 5\r\n\r\n'+(b'hell' if case=='truncated' else b'hello')
                tls.sendall(response)
                if case=='stall-close': time.sleep(.75)
                if case in ('raw-eof','media-raw-eof','cgi-eof','cgi-chunk-eof','cgi-truncated-eof','media-truncated-eof','raw-close-eof'): os.close(tls.detach());tls=None
                else:
                    raw=tls.unwrap();tls=None;raw.close()
            except (ssl.SSLError,ConnectionError,TimeoutError,OSError) as exc:
                server_errors.append(type(exc).__name__)
            except BaseException as exc:
                server_errors.append(repr(exc))
            finally:
                if tls is not None: tls.close()
                listener.close()
        worker=threading.Thread(target=serve,daemon=True);worker.start()
        trust='wrong' if case in ('untrusted','hostname') else 'good'
        now=int(time.time())+(172800 if case=='expired' else 0)
        expected=case in ('fixed','chunked','close','cgi-login','cgi-device-limit','media-stream','cgi-eof','cgi-chunk-eof','raw-eof','media-raw-eof')
        mode={'cancel':1,'deadline':2,'untrusted':3,'hostname':4,'expired':5,
              'raw-eof':6,'truncated':7,'late-cancel':8,'stall-close':10,'cgi-login':11,'cgi-device-limit':12,'media-stream':13,'media-raw-eof':14,'cgi-eof':15,'cgi-chunk-eof':16,'cgi-truncated-eof':17,'media-truncated-eof':18,'raw-close-eof':19}.get(case,0)
        run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),
                            '--library-path',str(lib)+':'+str(rt.parent),str(app),str(port),
                            str(tmp/(trust+'.der')),str(now),str(int(expected)),str(mode)],
                           cwd=ROOT,capture_output=True,text=True,timeout=25)
        worker.join(9)
        (work/(case+'.trace')).write_text(run.stderr)
        assert not worker.is_alive(),case
        assert run.returncode==0,(case,run.returncode,run.stderr[-5000:],server_errors)
        assert all(e in ('SSLError','SSLEOFError','ConnectionResetError','BrokenPipeError','TimeoutError') for e in server_errors),(case,server_errors)
        if expected: assert observed,case
        network=[s for s in run.stderr.splitlines() if re.search(r'\b(?:connect|sendto)\(',s,re.I)]
        assert network and all('127.0.0.1' in s for s in network),(case,network)
        if case in ('untrusted','hostname','expired'): assert not observed,case
        rows.append({'case':case,'passed':True,'request_observed':bool(observed)})
report={'passed':True,'cases':rows,'real_account_tested':False,'device_tested':False,
        'objective_complete':False,'ready_to_flash':False,
        'artifact_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),
        'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_qqmusic_tls.py']},
        'dependencies':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [crypto/'arm-build/libbearssl.a',rt,rt.parent/'libpthread.so.0',lib/'libc.so.6',lib/'ld-linux.so.3']},
        'limits':['Local loopback TLS with ephemeral test trust only.','No production CA selection, DNS, Wi-Fi or real account.','Test entropy only in fixture; caller owns engine configuration and socket.']}
(work/('report-framed-http.json' if '--framed-http' in sys.argv else 'report-cgi-framed.json' if '--cgi-framed' in sys.argv else 'report.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':rows},indent=2))
