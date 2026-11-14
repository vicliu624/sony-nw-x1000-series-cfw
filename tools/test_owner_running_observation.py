"""Original owner-loop step boundary with real observer IPC and modeled slow IO."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time
from player_arm_guest import stock_libraries

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/owner-running-observation' / str(time.time_ns())
OUT.mkdir(parents=True)
source = ROOT / 'runtime/apps/wireless-remote/rf_owner.c'
text = source.read_text(encoding='utf-8')


def function(name, required=True):
    begin = text.find('static int ' + name + '(')
    if begin < 0:
        if required:
            raise ValueError('Missing owner function: ' + name)
        return ''
    brace = text.index('{', begin)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]


starting = text.index(' puts("REMOTE_RF_OWNER_STARTING")')
state_begin = text.index('\n', starting) + 1
loop = text.index(' for(;;){\n', state_begin)
begin = loop + len(' for(;;){\n')
end = text.index('#ifdef XNOW_REMOTE_MODE_VIEW\n  if(rc>0)pairing_queue_report(now);', begin)
loop_state = text[state_begin:loop]
step = text[begin:end]
assert step.count('xnow_owner_runtime_step_with_controller') == 1
fixture_path = ROOT / 'tools/fixtures/owner_running_observation.c'
fixture = fixture_path.read_text(encoding='utf-8')
fixture = fixture.replace('/* ACTUAL_OBSERVER_FUNCTIONS */', '\n'.join((
    function('owner_mode_await'), function('owner_mode_recheck'),
    function('owner_mode_after_step', required=False))))
fixture = fixture.replace('/* ACTUAL_OWNER_STEP */', step)
fixture = fixture.replace('/* ACTUAL_OWNER_LOOP_STATE */', loop_state)
generated = OUT / 'actual-running-observation.c'
generated.write_text(fixture, encoding='utf-8')
sources = [str(generated.relative_to(ROOT)), 'runtime/apps/wireless-remote/owner_admission.c',
           'runtime/platform/wireless/mode_client.c', 'runtime/platform/wireless/mode_channel.c',
           'runtime/platform/wireless/mode_policy.c', 'runtime/store/stock_fs_bridge.c',
           'runtime/store/stock_stat64.c']
inputs = [*sources, source.relative_to(ROOT).as_posix(), fixture_path.relative_to(ROOT).as_posix(),
          'tools/test_owner_running_observation.py', 'runtime/apps/wireless-remote/owner_admission.h']
inputs += [p.relative_to(ROOT).as_posix() for d in ('runtime/platform/wireless','runtime/platform/espnow')
           for p in (ROOT/d).glob('*.h')]
inputs += ['runtime/platform/player/wireless_host.h','runtime/store/target_abi.h',
           'runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h']
inputs = sorted(set(inputs))
report = dict(passed=False, device_accessed=False, firmware_created=False,
              real_observer_datagrams=True, actual_owner_loop_step_slice=True,
              runtime_step_and_radio_effects_modeled=True,
              source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
              checks=[])


def run(name, command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    path = OUT / (name + '.log')
    path.write_text(result.stdout + result.stderr, encoding='utf-8')
    report['checks'].append(dict(name=name, exit_code=result.returncode,
                                 log=path.relative_to(ROOT).as_posix()))
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if result.returncode:
        raise RuntimeError(name + ' failed: ' + str(path))
    return result.stdout


flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation', '-I', str(ROOT)]
host = OUT / 'test.host'
run('host-build', ['gcc', *flags, '-fsanitize=address,undefined', '-pthread', *sources, '-o', str(host)])
host_output = run('host', [str(host)])
libs = stock_libraries()
arm = OUT / 'test.arm'
run('arm-build', ['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC',
                  '-D_DEFAULT_SOURCE=', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                  '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin', '-fno-pie',
                  '-fno-stack-protector', '-no-pie', '-nostdlib', '-Wl,--hash-style=sysv,--build-id=none',
                  *sources, 'runtime/store/start.c', 'runtime/store/start.S',
                  str(libs['libpthread.so.0']), str(libs['libc.so.6']), str(libs['ld-linux.so.3']),
                  '-lgcc', '-o', str(arm)])
search = ':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
arm_output = run('arm', ['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                        '--library-path', search, str(arm)])
assert 'OWNER_RUNNING_OBSERVATION_PASS' in host_output and 'OWNER_RUNNING_OBSERVATION_PASS' in arm_output
expected=['slow-ready-round','fast-rounds-no-extra-query','already-refreshed-no-duplicate-query',
          'queued-old-reply-needs-new-serial','queued-old-reply-policy-denied','parent-query-timeout',
          'replacement-lease-not-resumed','local-stop-not-resumed','runtime-error-not-rechecked',
          'stopping-controller-not-rechecked','revoked-before-entry-not-resumed','idle-timeout-unchanged',
          'clock-regression-not-resumed','revoked-during-round-not-resumed']
for output in (host_output,arm_output):
    assert re.findall(r'^RUNNING_OBSERVATION_CASE (.+)$',output,re.M)==expected
report['cases']=expected
report['fast_rounds']=100
report['fast_round_clock_reads']=100
report['idle_timeout_unchanged']=True
report['passed'] = True
report['limits'] = ['The runtime call duration is modeled; this is not measured device latency.',
                    'The actual owner-loop boundary and observer functions execute over real local datagrams.',
                    'No physical RF, sleep, USB, original audio or firmware installation is qualified.']
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(passed=True, report=(OUT / 'report.json').relative_to(ROOT).as_posix())))
