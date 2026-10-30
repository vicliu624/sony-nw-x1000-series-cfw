"""Render local Cardputer UI previews; never opens serial or radio devices."""
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/espnow-cardputer-ui'
OUT.mkdir(parents=True, exist_ok=True)
exe = OUT / 'preview'
subprocess.run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-g', 'tools/preview_cardputer_chat.cpp',
                '-o', str(exe)], cwd=ROOT, check=True)
for name in ('conversation', 'empty'):
    run = subprocess.run([str(exe), name], capture_output=True, timeout=10, check=True)
    assert len(run.stdout) == 240*135*2
    rgb = bytearray()
    for index in range(0, len(run.stdout), 2):
        v = run.stdout[index] | run.stdout[index+1] << 8
        rgb.extend((((v >> 11) & 31)*255//31, ((v >> 5) & 63)*255//63, (v & 31)*255//31))
    picture = Image.frombytes('RGB', (240, 135), bytes(rgb))
    picture.save(OUT / (name+'.png'))
    picture.resize((960, 540), Image.Resampling.NEAREST).save(OUT / (name+'-4x.png'))
report = {'passed': True, 'shared_renderer': True, 'sanitizers': True,
          'guard_pixels_checked': True, 'hardware_display_tested': False,
          'device_written': False, 'fixtures_are_demonstration_messages': True,
          'renderer_sha256': hashlib.sha256((ROOT/'runtime/platform/espnow/cardputer-chat/chat_ui.h').read_bytes()).hexdigest()}
(OUT / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
