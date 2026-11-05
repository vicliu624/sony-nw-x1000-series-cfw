"""Legacy DES known-answer, rejection paths and exact Sony container rebuild."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from app_registry import ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
from upg_crypto import encrypt_verified, decrypt_verified
from upg import unpack, STOCK_SHA256
from release_firmware import pack

key = bytes.fromhex('133457799bbcdff1')
plain = bytes.fromhex('0123456789abcdef')
encrypted = bytes.fromhex('85e813540f0ab405')
assert encrypt_verified(plain, key) == encrypted
assert decrypt_verified(encrypted, key) == plain
for value in (b'x', bytearray(8)):
    try:
        encrypt_verified(value, key)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid input accepted')
with patch('upg_crypto.subprocess.run', side_effect=FileNotFoundError) as run:
    try:
        encrypt_verified(plain, key)
    except ValueError:
        assert run.call_count == 1
    else:
        raise AssertionError('Missing backend accepted')
with patch('upg_crypto.subprocess.run', return_value=subprocess.CompletedProcess([], 0, b'\0' * 8)):
    try:
        encrypt_verified(plain, key)
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong roundtrip accepted')
parts = [(ROOT / ('work/upg-jp/verified-' + str(i) + '.bin')).read_bytes() for i in range(4)]
rebuilt = pack(parts)
assert hashlib.sha256(rebuilt).hexdigest() == STOCK_SHA256
assert unpack(rebuilt)[1] == parts
report = dict(passed=True, known_des_answer=True, no_retry_on_backend_error=True,
              invalid_input_and_roundtrip_rejected=True, stock_upg_byte_exact=True,
              device_accessed=False, hardware_qualified=False,
              source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in ('scripts/upg_crypto.py', 'scripts/upg.py',
                                          'tools/release_firmware.py', 'tools/test_upg_crypto.py')})
out = ROOT / 'work/upg-crypto-check'
out.mkdir(exist_ok=True)
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
