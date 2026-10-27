"""Offline ARM login coordination tests; never uses network or player devices."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / 'work/qqmusic-session'
work.mkdir(parents=True, exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib = ROOT / 'work/arm-signal-tests/lib'
for name, digest in {
    'libc.so.6': '5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3': '2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    if hashlib.sha256((lib/name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Stock runtime hash mismatch')
sources = ['runtime/apps/qqmusic/qqmusic_session.c', 'tools/fixtures/qqmusic_session.c',
           'runtime/store/start.c', 'runtime/store/start.S']
def build_run(name, inputs):
    app = work / name
    subprocess.run(['arm-linux-gnueabi-gcc', '-std=c99', '-Os', '-Wall', '-Wextra',
               '-Werror', '-march=armv5te', '-marm', '-mfloat-abi=soft',
               '-ffreestanding', '-fno-builtin', '-fno-pie', '-nostdlib', '-no-pie',
               '-Wl,--hash-style=sysv', '-Wl,--build-id=none',
               '-Wl,--dynamic-linker=/lib/ld-linux.so.3', *inputs,
               str(lib/'libc.so.6'), str(lib/'ld-linux.so.3'), '-lgcc',
               '-o', str(app)], cwd=ROOT, check=True)
    subprocess.run(['qemu-arm', '-cpu', 'arm926', str(lib/'ld-linux.so.3'),
                '--library-path', str(lib), str(app)], cwd=ROOT, check=True,
               timeout=15)
    return hashlib.sha256(app.read_bytes()).hexdigest()
artifacts = {'session-tests.arm': build_run('session-tests.arm', sources)}
protocol = ['runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
            'runtime/store/stock_tls_compat.c', 'tools/fixtures/qqmusic_protocol.c',
            'runtime/store/start.c', 'runtime/store/start.S']
artifacts['protocol-tests.arm'] = build_run('protocol-tests.arm', protocol)
cookies = ['runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
           'runtime/apps/qqmusic/qqmusic_cookie.c', 'runtime/store/stock_tls_compat.c',
           'tools/fixtures/qqmusic_cookie.c', 'runtime/store/start.c', 'runtime/store/start.S']
artifacts['cookie-tests.arm'] = build_run('cookie-tests.arm', cookies)
http = [p for p in cookies if p != 'tools/fixtures/qqmusic_cookie.c']
http += ['runtime/apps/qqmusic/qqmusic_http.c', 'tools/fixtures/qqmusic_http.c']
artifacts['http-tests.arm'] = build_run('http-tests.arm', http)
response = [p for p in http if p != 'tools/fixtures/qqmusic_http.c']
response += ['runtime/apps/qqmusic/qqmusic_response.c', 'runtime/native/sha256.c', 'tools/fixtures/qqmusic_response.c']
artifacts['response-tests.arm'] = build_run('response-tests.arm', response)
json_sources = ['runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
                'runtime/apps/qqmusic/qqmusic_json.c', 'runtime/apps/qqmusic/qqmusic_credential.c',
                'runtime/apps/qqmusic/qqmusic_cgi.c', 'runtime/apps/qqmusic/qqmusic_cookie.c', 'runtime/apps/qqmusic/qqmusic_http.c',
                'runtime/store/stock_tls_compat.c', 'tools/fixtures/qqmusic_json.c',
                'runtime/store/start.c', 'runtime/store/start.S']
artifacts['json-tests.arm'] = build_run('json-tests.arm', json_sources)
login_sources = [p for p in json_sources if p != 'tools/fixtures/qqmusic_json.c']
login_sources += ['runtime/apps/qqmusic/qqmusic_login.c', 'runtime/apps/qqmusic/qqmusic_response.c', 'runtime/native/sha256.c', 'tools/fixtures/qqmusic_login.c']
artifacts['login-tests.arm'] = build_run('login-tests.arm', login_sources)
host = work/'protocol-tests.sanitized'
subprocess.run(['gcc', '-std=c99', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                'runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
                'tools/fixtures/qqmusic_protocol.c', '-o', str(host)], cwd=ROOT, check=True)
subprocess.run([str(host)], cwd=ROOT, check=True, timeout=15)
cookie_host = work/'cookie-tests.sanitized'
subprocess.run(['gcc', '-std=c99', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                'runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
                'runtime/apps/qqmusic/qqmusic_cookie.c', 'tools/fixtures/qqmusic_cookie.c',
                '-o', str(cookie_host)], cwd=ROOT, check=True)
subprocess.run([str(cookie_host)], cwd=ROOT, check=True, timeout=15)
http_host = work/'http-tests.sanitized'
subprocess.run(['gcc', '-std=c99', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                'runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
                'runtime/apps/qqmusic/qqmusic_cookie.c', 'runtime/apps/qqmusic/qqmusic_http.c',
                'tools/fixtures/qqmusic_http.c', '-o', str(http_host)], cwd=ROOT, check=True)
subprocess.run([str(http_host)], cwd=ROOT, check=True, timeout=15)
response_host = work/'response-tests.sanitized'
subprocess.run(['gcc', '-std=c99', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                'runtime/apps/qqmusic/qqmusic_session.c', 'runtime/apps/qqmusic/qqmusic_protocol.c',
                'runtime/apps/qqmusic/qqmusic_cookie.c', 'runtime/apps/qqmusic/qqmusic_http.c',
                'runtime/apps/qqmusic/qqmusic_response.c', 'runtime/native/sha256.c', 'tools/fixtures/qqmusic_response.c',
                '-o', str(response_host)], cwd=ROOT, check=True)
subprocess.run([str(response_host)], cwd=ROOT, check=True, timeout=15)
json_host = work/'json-tests.sanitized'
subprocess.run(['gcc', '-std=c99', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                *[p for p in json_sources if p not in ('runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S')],
                '-o', str(json_host)], cwd=ROOT, check=True)
subprocess.run([str(json_host)], cwd=ROOT, check=True, timeout=15)
tracked = sources + ['runtime/apps/qqmusic/qqmusic_session.h', 'tools/test_qqmusic_session.py']
tracked += protocol + ['runtime/apps/qqmusic/qqmusic_protocol.h']
tracked += cookies + ['runtime/apps/qqmusic/qqmusic_cookie.h']
tracked += http + ['runtime/apps/qqmusic/qqmusic_http.h']
tracked += response + ['runtime/apps/qqmusic/qqmusic_response.h']
tracked += json_sources + ['runtime/apps/qqmusic/qqmusic_json.h', 'runtime/apps/qqmusic/qqmusic_credential.h', 'runtime/apps/qqmusic/qqmusic_cgi.h']
tracked += login_sources + ['runtime/apps/qqmusic/qqmusic_login.h']
report = {'passed': True, 'scope': 'synthetic login coordinator and protocol boundaries',
          'real_account_tested': False, 'device_tested': False,
          'objective_complete': False, 'ready_to_flash': False,
          'checks': ['scan/exchange/verify ordering', 'old generation rejection',
                     'cancelled callback rejection', 'deadline boundary',
                     'denial and network failure', 'QR expiration',
                     'clock and generation overflow', 'QR token vector',
                     'QQ QR/poll/check_sig/OAuth request builders',
                     'bounded callback grammar and truncated prefixes',
                     'untrusted host, duplicate key, script and injection rejection',
                     'OAuth state matching and secret clearing',
                     'host ASan/UBSan deterministic mutated callback corpus',
                     'cookie domain/path scope, expiry, deletion, limits and atomic failure',
                     'host ASan/UBSan cookie tests',
                     'HTTP headers: redirect cookies, body offset, conflicting framing and truncation',
                     'host ASan/UBSan HTTP header tests',
                     'response fixed/chunked/close framing across every split and bytewise input',
                     'transactional cookies, truncated bodies, overflow, cancel and excess bytes',
                     'host ASan/UBSan response tests',
                     'JSON UTF-8, surrogate pairs, duplicate decoded keys, grammar and exact uint64',
                     'credential envelope, business errors and invalid/missing fields',
                     'host ASan/UBSan JSON and credential tests'],
          'artifact_sha256': artifacts,
          'sources': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}}
(work/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
