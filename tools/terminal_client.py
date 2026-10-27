"""PC-only client for X1060 WiFi Terminal. Python 3 standard library only."""
import argparse
import contextlib
import getpass
import hashlib
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import ssl
import struct
import sys
import threading
import time

def frame(kind, data):
    if kind not in (b'D', b'W') or not 0 < len(data) <= 4096:
        raise ValueError('invalid frame')
    return kind + struct.pack('!H', len(data)) + data

def connect(host, port, pin_path, code):
    pin = Path(pin_path).read_text(encoding='ascii').strip().lower()
    if len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
        raise ValueError('invalid certificate fingerprint file')
    if len(code) != 32 or any(c not in '0123456789abcdef' for c in code.lower()):
        raise ValueError('connection code must be the 32 hex characters shown on the player')
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Authentication uses an exact SHA-256 certificate pin before sending secrets;
    # device RTC and certificate DNS names are not trusted for this local service.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256')
    raw = socket.create_connection((host, port), timeout=10)
    try:
        sock = ctx.wrap_socket(raw, server_hostname=None)
    except BaseException:
        raw.close()
        raise
    try:
        actual = hashlib.sha256(sock.getpeercert(binary_form=True)).hexdigest()
        if actual != pin:
            raise ssl.SSLError('certificate fingerprint mismatch: connection refused')
        sock.sendall(b'XTERM1 ' + code.lower().encode('ascii') + b'\n')
        return sock
    except BaseException:
        sock.close()
        raise

def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count-len(data))
        if not part:
            raise EOFError('session closed')
        data.extend(part)
    return bytes(data)

def receive(sock):
    head = recv_exact(sock, 3)
    n = struct.unpack('!H', head[1:])[0]
    if head[:1] != b'D' or not 0 < n <= 4096:
        raise ValueError('invalid server frame')
    return recv_exact(sock, n)

def execute(sock, command, timeout=30):
    """Text command mode for PC automation; stdout/stderr share the remote PTY."""
    if not command or '\0' in command or len(command.encode('utf-8'))>3000:
        raise ValueError('command must be nonempty text, at most 3000 UTF-8 bytes')
    token=secrets.token_hex(16).encode('ascii')
    begin=b'\r\nHB_BEGIN_'+token+b'\r\n'
    end=re.compile(b'\r\nHB_END_'+token+rb':([0-9]{1,3})\r\n')
    # Sony's small BusyBox ash has echo but no printf applet/builtin.
    script=(b"stty -echo; PS1=; PS2=; echo; echo HB_BEGIN_"+token+b"; (\n"+command.encode('utf-8')+b"\n); hb_result=$?; echo; echo \"HB_END_"+token+b":$hb_result\"; exit\n")
    sock.settimeout(timeout)
    sock.sendall(frame(b'D',script))
    data=bytearray();started=False;deadline=time.monotonic()+timeout
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError('remote command timed out; connection closed')
        sock.settimeout(remaining)
        data.extend(receive(sock))
        if len(data)>64*1024*1024:
            raise ValueError('command output exceeds 64 MiB')
        if not started:
            pos=data.find(begin)
            if pos<0:
                continue
            del data[:pos+len(begin)];started=True
        match=end.search(data)
        if match:
            return bytes(data[:match.start()]),int(match[1])

@contextlib.contextmanager
def terminal_mode():
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-11)
        input_handle = kernel.GetStdHandle(-10)
        old = ctypes.c_uint()
        old_input = ctypes.c_uint()
        changed = bool(kernel.GetConsoleMode(handle, ctypes.byref(old)))
        input_changed = bool(kernel.GetConsoleMode(input_handle, ctypes.byref(old_input)))
        if changed:
            kernel.SetConsoleMode(handle, old.value | 4)
        if input_changed:
            kernel.SetConsoleMode(input_handle, (old_input.value & ~(1|2|4|64)) | 128)
        try:
            yield
        finally:
            if changed:
                kernel.SetConsoleMode(handle, old.value)
            if input_changed:
                kernel.SetConsoleMode(input_handle, old_input.value)
    else:
        import termios
        import tty
        old = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin)
            yield
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)

def keyboard(items, stop):
    if os.name == 'nt':
        import msvcrt
        mapping = {'H':b'\x1b[A','P':b'\x1b[B','K':b'\x1b[D','M':b'\x1b[C','G':b'\x1b[H','O':b'\x1b[F','S':b'\x1b[3~'}
        while not stop.is_set():
            if not msvcrt.kbhit():
                time.sleep(.01)
                continue
            c = msvcrt.getwch()
            data = mapping.get(msvcrt.getwch(), b'') if c in ('\x00','\xe0') else c.encode('utf-8',errors='replace')
            if data == b'\x1d':
                stop.set()
                return
            if data:
                items.put(data)
    else:
        import select
        while not stop.is_set():
            if not select.select([sys.stdin], [], [], .1)[0]:
                continue
            data = os.read(sys.stdin.fileno(), 4096)
            if not data or b'\x1d' in data:
                stop.set()
                return
            items.put(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    parser.add_argument('--port', type=int, default=2323)
    parser.add_argument('--pin', default=str(Path(__file__).with_name('server-cert.sha256')))
    parser.add_argument('--command',help='run a text command, print output and return its exit status')
    parser.add_argument('--code-file',help='PC file holding the current player connection code; avoids secrets in command arguments')
    parser.add_argument('--timeout',type=float,default=30,help='command deadline in seconds (default: 30)')
    args = parser.parse_args()
    if not 0<args.timeout<=86400:
        parser.error('timeout must be between 0 and 86400 seconds')
    if args.command is None and not sys.stdin.isatty():
        parser.error('use an interactive terminal')
    if args.code_file:
        code=Path(args.code_file).read_text(encoding='ascii').strip().replace(' ','')
    else:
        if not sys.stdin.isatty():
            parser.error('noninteractive command mode requires --code-file')
        code = getpass.getpass('Player connection code (32 hex characters): ').replace(' ', '')
    with connect(args.host,args.port,args.pin,code) as sock:
        if args.command is not None:
            output,status=execute(sock,args.command,args.timeout)
            sys.stdout.buffer.write(output);sys.stdout.buffer.flush()
            return status
        print('Certificate verified. Ctrl-] disconnects; Ctrl-C is sent to the player.')
        # Only this thread ever uses the SSL socket. Nonblocking SSL reads and
        # writes must not run concurrently on one Python SSL object.
        sock.setblocking(False)
        items, stop = queue.Queue(maxsize=256), threading.Event()
        thread = threading.Thread(target=keyboard,args=(items,stop),daemon=True)
        incoming = bytearray()
        pending = bytearray()
        inflight = None
        previous = None
        with terminal_mode():
            thread.start()
            try:
                while not stop.is_set():
                    size = shutil.get_terminal_size((80,24))
                    window = (min(500,max(1,size.lines)),min(500,max(1,size.columns)))
                    if window != previous:
                        pending.extend(frame(b'W',struct.pack('!HH',*window)))
                        previous = window
                    if len(pending) < 65536:
                        try:
                            pending.extend(frame(b'D',items.get_nowait()))
                        except queue.Empty:
                            pass
                    if pending:
                        if inflight is None:
                            inflight = bytes(pending[:4096])
                        try:
                            n = sock.send(inflight)
                            del pending[:n]
                            inflight = None
                        except (ssl.SSLWantReadError,ssl.SSLWantWriteError):
                            pass
                    try:
                        data = sock.recv(16384)
                        if not data:
                            break
                        incoming.extend(data)
                    except (ssl.SSLWantReadError,ssl.SSLWantWriteError):
                        pass
                    while len(incoming) >= 3:
                        n = struct.unpack('!H',incoming[1:3])[0]
                        if incoming[0] != ord('D') or not 0 < n <= 4096:
                            raise ValueError('invalid server frame')
                        if len(incoming) < n+3:
                            break
                        sys.stdout.buffer.write(incoming[3:3+n])
                        sys.stdout.buffer.flush()
                        del incoming[:n+3]
                    time.sleep(.005)
            finally:
                stop.set()
                thread.join(timeout=.3)
    print('\nDisconnected.')

if __name__ == '__main__':
    try:
        sys.exit(main() or 0)
    except (OSError,ValueError,EOFError) as error:
        print(f'Connection failed: {error}',file=sys.stderr)
        sys.exit(1)
