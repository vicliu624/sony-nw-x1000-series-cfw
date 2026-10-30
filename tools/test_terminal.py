"""Real loopback TLS + host PTY acceptance, including ARM under stock libc.
No player, WiFi hardware, system partition or raw device is accessed.
"""
from pathlib import Path
import hashlib
import hmac
import importlib.util
import json
import os
import select
import signal
import socket
import ssl
import struct
import subprocess
import sys
import time
import tempfile
import shutil

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/terminal-review'
folder=WORK/'package/HOMEBREW/apps/terminal'
spec=importlib.util.spec_from_file_location('terminal_client',ROOT/'tools/terminal_client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
checks=[]
stable_codes=[]
def until(sock,needle,timeout=10):
    end=time.monotonic()+timeout;out=bytearray()
    sock.settimeout(timeout)
    while needle not in out:
        if time.monotonic()>end:raise AssertionError(bytes(out))
        out.extend(client.receive(sock))
    return bytes(out)

def running(pid):
    try:
        text=Path(f'/proc/{pid}/stat').read_text()
        return text.split(') ',1)[1][0]!='Z'
    except FileNotFoundError:
        return False

def console_until(fd,needle,timeout=10):
    end=time.monotonic()+timeout;data=bytearray()
    while needle not in data:
        left=end-time.monotonic()
        assert left>0,bytes(data)
        if select.select([fd],[],[],left)[0]:data.extend(os.read(fd,65536))
    return bytes(data)

for kind in ('host','arm'):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    cmd=[str(WORK/'server-tests.host')] if kind=='host' else ['qemu-arm','-cpu','arm926',str(ROOT/'work/arm-signal-tests/lib/ld-linux.so.3'),'--library-path',str(ROOT/'work/arm-signal-tests/lib'),str(WORK/'server-tests.arm')]
    log=open(WORK/(kind+'-stderr.log'),'wb')
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1')
    server=subprocess.Popen(cmd+[str(folder),str(port)],stdout=subprocess.PIPE,stderr=log,env=env)
    try:
        assert select.select([server.stdout],[],[],15)[0],'server startup timeout'
        ready=server.stdout.readline().decode().strip()
        assert ready.startswith('READY '),ready
        code=ready.split()[1];assert len(code)==32
        expected=hmac.new((folder/'server-key.der').read_bytes(),b'X1000-WIFI-TERMINAL-CODE-v1',hashlib.sha256).hexdigest()[:32]
        assert hmac.compare_digest(code,expected),'device code differs from independent HMAC reference'
        stable_codes.append(code)
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        # Pin failure happens before any auth secret is sent.
        badpin=WORK/'bad-pin.sha256';badpin.write_text('0'*64+'\n')
        try:client.connect('127.0.0.1',port,badpin,code)
        except ssl.SSLError:pass
        else:raise AssertionError('incorrect certificate accepted')
        time.sleep(1.2)
        wrong=client.connect('127.0.0.1',port,WORK/'server-cert.sha256','0'*32)
        wrong.settimeout(5)
        try:response=wrong.recv(1);assert not response,response
        except (ssl.SSLError,ConnectionResetError):pass
        wrong.close();time.sleep(1.2)
        sock=client.connect('127.0.0.1',port,WORK/'server-cert.sha256',code)
        until(sock,b'Ctrl-C interrupts.')
        # Frame fragmentation at every header boundary and partial payload.
        command=client.frame(b'D',b"printf '__INTERACTIVE_OK__\\n'\n")
        for part in (command[:1],command[1:2],command[2:4],command[4:]):sock.sendall(part);time.sleep(.01)
        until(sock,b'__INTERACTIVE_OK__\r\n')
        sock.sendall(client.frame(b'D',b"cd /; printf '__PWD__'; pwd\n"))
        until(sock,b'__PWD__/\r\n')
        sock.sendall(client.frame(b'D',b"cd; printf '__HOME__'; pwd; printf '__TMP__%s_END__\\n' \"$TMPDIR\"\n"))
        home=until(sock,b'_END__\r\n');assert str(folder).encode() in home,home
        sock.sendall(client.frame(b'D',b"printf '__BULK_BEGIN__'; head -c 65536 /dev/zero | tr '\\000' Z; printf '__BULK_END__\\n'\n"))
        bulk=until(sock,b'__BULK_END__\r\n',15)
        assert b'Z'*65536 in bulk,'large output was truncated or corrupted'
        sock.sendall(client.frame(b'W',struct.pack('!HH',37,111))+client.frame(b'D',b"stty size; printf '__SIZE_END__\\n'\n"))
        output=until(sock,b'__SIZE_END__\r\n');assert b'37 111' in output,output
        sock.sendall(client.frame(b'D',b"sleep 20; printf '__INTERRUPTED__\\n'\n"));time.sleep(.3)
        sock.sendall(client.frame(b'D',b'\x03'))
        sock.sendall(client.frame(b'D',b"printf '__AFTER_CTRL_C__\\n'\n"))
        until(sock,b'__AFTER_CTRL_C__\r\n',5)
        sock.sendall(client.frame(b'D',b"printf '__PID_%s_END__\\n' $$\n"))
        result=until(sock,b'_END__\r\n')
        import re
        match=re.search(rb'__PID_(\d+)_END__\r\n',result);assert match,result
        shell=int(match[1]);assert running(shell)
        sock.close();time.sleep(.6);assert not running(shell),'shell survived disconnect'
        time.sleep(1.1)
        # Reconnection, malformed oversized frame and teardown.
        sock=client.connect('127.0.0.1',port,WORK/'server-cert.sha256',code)
        until(sock,b'Ctrl-C interrupts.')
        sock.sendall(b'D\xff\xff');sock.settimeout(5)
        try:
            while sock.recv(4096):pass
        except (ssl.SSLError,ConnectionResetError):pass
        sock.close();time.sleep(1.2)
        normal=client.connect('127.0.0.1',port,WORK/'server-cert.sha256',code)
        until(normal,b'Ctrl-C interrupts.')
        normal.sendall(client.frame(b'D',b"printf '__FINAL_OUTPUT_BEFORE_EXIT__\\n'; exit\n"))
        until(normal,b'__FINAL_OUTPUT_BEFORE_EXIT__\r\n')
        normal.settimeout(5)
        try:
            while normal.recv(4096):pass
        except (ssl.SSLError,ConnectionResetError):pass
        normal.close();time.sleep(.3)
        codefile=WORK/'test-code.private.txt';codefile.write_text(code+'\n');codefile.chmod(0o600)
        try:
            machine=subprocess.run([sys.executable,str(ROOT/'tools/terminal_client.py'),'127.0.0.1','--port',str(port),'--pin',str(WORK/'server-cert.sha256'),'--code-file',str(codefile),'--command',"printf 'AUTOMATION_OK\\n'; exit 7"],capture_output=True,timeout=10)
            assert machine.returncode==7,(machine.returncode,machine.stdout,machine.stderr)
            assert machine.stdout==b'AUTOMATION_OK\r\n',machine.stdout
        finally:
            codefile.unlink(missing_ok=True)
        time.sleep(.3)
        if kind=='host':
            # Exercise the shipped interactive Python client, not just helpers.
            import pty
            import fcntl
            import termios
            master,slave=pty.openpty()
            def controlling_console():
                os.setsid()
                fcntl.ioctl(0,termios.TIOCSCTTY,0)
            computer=subprocess.Popen([sys.executable,str(ROOT/'tools/terminal_client.py'),'127.0.0.1','--port',str(port),'--pin',str(WORK/'server-cert.sha256')],stdin=slave,stdout=slave,stderr=slave,preexec_fn=controlling_console)
            os.close(slave)
            try:
                console_until(master,b'characters): ')
                os.write(master,code.encode()+b'\n')
                console_until(master,b'Ctrl-C interrupts.')
                os.write(master,b"printf '\\n__FULL_CLIENT_OK__\\n'\r")
                console_until(master,b'\r\n__FULL_CLIENT_OK__\r\n')
                os.write(master,b'\x1d')
                assert computer.wait(timeout=5)==0
            finally:
                if computer.poll() is None:computer.terminate();computer.wait(timeout=5)
                os.close(master)
            time.sleep(1.2)
            checks.append('Shipped PC interactive client under real console PTY: secret prompt, encrypted connection, keyboard forwarding, command output and Ctrl-] disconnect')
        sock=client.connect('127.0.0.1',port,WORK/'server-cert.sha256',code)
        until(sock,b'Ctrl-C interrupts.')
        sock.sendall(client.frame(b'D',b"printf '__PID_%s_END__\\n' $$\n"))
        result=until(sock,b'_END__\r\n');match=re.search(rb'__PID_(\d+)_END__\r\n',result);assert match,result
        shell=int(match[1])
        server.terminate();assert server.wait(timeout=5)==0
        sock.close();time.sleep(.2);assert not running(shell),'shell survived app shutdown'
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        assert before==after,'terminal created or modified application files'
        checks.append(kind+': real TLS1.2 pinned certificate, wrong-pin/wrong-code rejection, fragmented frames, real interactive shell/cd, 64KiB lossless output, final output and normal exit, PTY window resize, Ctrl-C, reconnect, oversized-frame rejection, disconnect/app-stop shell cleanup')
    finally:
        if server.poll() is None:server.terminate();server.wait(timeout=5)
        log.close()
    stderr=(WORK/(kind+'-stderr.log')).read_text()
    assert 'AddressSanitizer' not in stderr and 'runtime error:' not in stderr,stderr
assert len(set(stable_codes))==1,'same identity changed code across host/ARM process restart'
with tempfile.TemporaryDirectory(prefix='fixed-code-identity-',dir=WORK) as temporary:
    private=Path(temporary);other=private/'terminal';shutil.copytree(folder,other)
    key=private/'key.pem';certificate=private/'certificate.pem'
    for command in [
        ['openssl','ecparam','-name','prime256v1','-genkey','-noout','-out',str(key)],
        ['openssl','req','-new','-x509','-sha256','-days','1','-key',str(key),'-subj','/CN=Offline identity test/','-out',str(certificate)],
        ['openssl','ec','-in',str(key),'-outform','DER','-out',str(other/'server-key.der')],
        ['openssl','x509','-in',str(certificate),'-outform','DER','-out',str(other/'server-cert.der')]]:
        subprocess.run(command,capture_output=True,check=True)
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    other_server=subprocess.Popen([str(WORK/'server-tests.host'),str(other),str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert select.select([other_server.stdout],[],[],15)[0]
        ready=other_server.stdout.readline().decode().strip();assert ready.startswith('READY ')
        other_code=ready.split()[1]
        assert other_code!=stable_codes[0] and hmac.compare_digest(other_code,hmac.new((other/'server-key.der').read_bytes(),b'X1000-WIFI-TERMINAL-CODE-v1',hashlib.sha256).hexdigest()[:32])
    finally:
        other_server.terminate();assert other_server.wait(timeout=5)==0
checks.append('Fixed identity code matches independent HMAC-SHA256 and remains identical across host/ARM service restarts; no code persisted or echoed in report')
checks.append('A separately generated personal device identity produces a different fixed code')
report={'passed':True,'physical_device_access':False,'checks':checks,'limitations':['Both tests use a development-PC Linux PTY and /bin/sh; ARM test uses actual ARM926 candidate service with original Sony libc through QEMU user mode.','No X1060 WiFi, framebuffer, entropy quality, permissions or shell behavior is hardware-qualified.']}
(WORK/'tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
