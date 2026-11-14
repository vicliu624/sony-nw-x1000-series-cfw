"""Exercise the composed Homebrew entry in a fresh, isolated Sony UI guest.

This is a software lifecycle check, not RF, audio, sleep or device qualification.
The external child is the explicit two-second fixture, not the real launcher.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]


def work_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT / 'work'):
        raise ValueError('Guest inputs and output must stay under work/')
    return path


def home_score(image, reference):
    # Exclude the status bar and its independently changing battery indicator.
    area = (0, 30, 240, 390)
    difference = ImageChops.difference(image.crop(area), reference.crop(area))
    pixels = list(difference.get_flattened_data() if hasattr(difference, 'get_flattened_data') else difference.getdata())
    return sum(max(pixel) <= 8 for pixel in pixels) / len(pixels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout-review', required=True)
    parser.add_argument('--home-reference', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--ncan-wait-model', action='store_true',
                        help='Explicit idle NCAN model; no NC engine or hardware qualification')
    parser.add_argument('--task-trace', action='store_true',
                        help='Read guest state while pausing scheduling; timing remains unqualified')
    parser.add_argument('--mg-constructor-model', action='store_true',
                        help='Existing empty MG constructor model; no crypto or key operations')
    args = parser.parse_args()
    if not 1 <= args.rounds <= 5 or not 10 <= args.timeout <= 120:
        parser.error('Use 1..5 rounds and a 10..120 second stage timeout')
    output = work_path(args.output)
    if output.exists():
        parser.error('Preserve prior evidence; choose a new output')
    output.mkdir(parents=True)
    reference_path = work_path(args.home_reference)
    with Image.open(reference_path) as source:
        reference = source.convert('RGB')
        if reference.size == (640, 480):
            reference = reference.crop((200, 24, 440, 456))
        if reference.size != (240, 432):
            raise ValueError('Expected a full CLCD or logical Sony Home reference')
    session = output / 'guest'
    command = [sys.executable, str(ROOT / 'tools/run_stock_gui.py'),
               '--output', session.relative_to(ROOT).as_posix(),
               '--layout-review', args.layout_review,
               '--ram-user-volume', '--homebrew-roundtrip-fixture', '--catalog-trace']
    if args.ncan_wait_model:
        command += ['--ncan-wait-model']
    if args.task_trace:
        command += ['--task-trace']
    if args.mg_constructor_model:
        command += ['--mg-constructor-model']
    report = dict(passed=False, device_accessed=False, firmware_created=False,
                  hardware_qualified=False, synthetic_child=True, command=command,
                  reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                  rounds=[], observations=[])
    test_source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['test_source_sha256'] = test_source
    server = None
    started = time.monotonic()
    with (output / 'viewer.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)

        def check_live():
            if process.poll() is not None:
                raise RuntimeError('Guest viewer exited; see viewer.log')

        def request(path, data=None):
            url = server['url'].rstrip('/') + path
            if data is None:
                query = urllib.request.Request(url)
            else:
                query = urllib.request.Request(url, data=json.dumps(data).encode(), method='POST',
                          headers={'Content-Type': 'application/json',
                                   'X-Control-Token': server['control_token']})
            with urllib.request.urlopen(query, timeout=10) as response:
                return response.read()

        def wait_home(stage):
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                check_live()
                try:
                    frame_bytes = request('/frame.png')
                except urllib.error.HTTPError as error:
                    if error.code != 503:
                        raise
                    time.sleep(.25)
                    continue
                with Image.open(io.BytesIO(frame_bytes)) as frame:
                    image = frame.convert('RGB')
                score = home_score(image, reference)
                report['observations'].append(dict(stage=stage,
                    seconds=round(time.monotonic() - started, 3), home_score=round(score, 6)))
                image.save(output / (stage + '-latest.png'))
                if score >= .92:
                    return score
                time.sleep(.25)
            raise RuntimeError(stage + ': Home was not observed within the stage timeout')

        try:
            # Preparation includes compilation; the UI timeout starts afterward.
            deadline = time.monotonic() + 180
            while not (session / 'server.json').exists():
                check_live()
                if time.monotonic() >= deadline:
                    raise RuntimeError('Guest preparation timed out')
                time.sleep(.25)
            server = json.loads((session / 'server.json').read_text(encoding='utf-8'))
            if not server['physical_device_access'] is False or not server['url'].startswith('http://127.0.0.1:'):
                raise ValueError('Expected only an isolated loopback guest')
            wait_home('boot')
            time.sleep(1)
            for index in range(args.rounds):
                before = (session / 'serial.log').read_bytes()
                entries = before.count(b'GUEST_HOMEBREW_ROUNDTRIP_CHILD_ENTERED')
                exits = before.count(b'GUEST_HOMEBREW_ROUNDTRIP_CHILD_EXITING')
                request('/touch', dict(x=120, y=332, down=1))
                time.sleep(.25)
                request('/touch', dict(x=120, y=332, down=0))
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    check_live()
                    current = (session / 'serial.log').read_bytes()
                    entered = current.count(b'GUEST_HOMEBREW_ROUNDTRIP_CHILD_ENTERED') > entries
                    exited = current.count(b'GUEST_HOMEBREW_ROUNDTRIP_CHILD_EXITING') > exits
                    if entered and exited:
                        break
                    time.sleep(.25)
                else:
                    report['rounds'].append(dict(index=index + 1, entered=entered, exited=exited))
                    raise RuntimeError('Synthetic child did not enter and exit')
                score = wait_home('return-' + str(index + 1))
                report['rounds'].append(dict(index=index + 1, entered=True, exited=True, home_score=score))
            report['passed'] = True
        except Exception as error:
            report['failure'] = str(error)
            if server is not None and process.poll() is None:
                try:
                    (output / 'failure.png').write_bytes(request('/frame.png'))
                except OSError:
                    pass
        finally:
            if server is not None and process.poll() is None:
                try:
                    request('/stop', {})
                except (OSError, ValueError):
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
            report['viewer_exit'] = process.returncode
            report['seconds'] = round(time.monotonic() - started, 3)
            report['viewer_closed'] = (session / 'viewer-ended.json').exists()
            prepared_path = session / 'prepared.json'
            sources = json.loads(prepared_path.read_text(encoding='utf-8'))['compiled_source_hashes'] if prepared_path.exists() else {}
            report['source_changes'] = [name for name, sha in sources.items()
                if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha]
            if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != test_source:
                report['source_changes'].append(Path(__file__).relative_to(ROOT).as_posix())
            if report['source_changes']:
                report['passed'] = False
                report['failure'] = 'Checked source changed during the run'
            (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('passed', 'rounds', 'viewer_closed')}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
