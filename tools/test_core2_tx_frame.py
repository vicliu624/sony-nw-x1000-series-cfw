"""Check fixed-header Core2 TX observation without a radio or firmware build."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'work/core2-tx-frame-tests' / str(time.time_ns())
out.mkdir(parents=True)
source = ROOT / 'tools/fixtures/core2_tx_frame_observation.c'
header = ROOT / 'runtime/apps/wireless-remote/core2/src/tx_frame_observation.h'
checks = []
for compiler, standard in (('gcc-12', 'c99'), ('g++-12', 'c++20')):
    binary = out / compiler
    subprocess.run([compiler, '-std=' + standard, '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(ROOT), str(source),
                    '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    (out / (compiler + '.log')).write_text(result.stdout + result.stderr)
    assert not result.returncode and 'CORE2_TX_FRAME_OBSERVATION_PASS' in result.stdout, result.stdout + result.stderr
    checks.append(dict(compiler=compiler, standard=standard, passed=True))
report = dict(passed=True, checks=checks, sanitizer_checks=True, device_accessed=False,
    source_hashes={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (source, header, Path(__file__).resolve())},
    limits=['Synthetic header layout and bounded reads; no physical callback buffer or air capture.'])
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, report=(out / 'report.json').relative_to(ROOT).as_posix())))
