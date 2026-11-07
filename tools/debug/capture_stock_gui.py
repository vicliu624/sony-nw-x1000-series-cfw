"""Capture the actual local QEMU CLCD; optional lossless PNG conversion."""
import argparse,json,re,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',required=True);p.add_argument('--stem',default='manual-clcd')
args=p.parse_args();session=(ROOT/args.session).resolve();assert session.is_relative_to(ROOT/'work')
assert re.fullmatch(r'[A-Za-z0-9_-]{1,60}',args.stem)
launch=json.loads((session/'launch.json').read_text());assert launch['physical_device_access'] is False
actual=Path(f"/proc/{launch['qemu_pid']}/cmdline").read_bytes().split(b'\0')
assert actual[:-1]==[v.encode() for v in launch['command']]
target=session/(args.stem+'.ppm')
with socket.create_connection(('127.0.0.1',launch['monitor_port']),timeout=3) as monitor:
 def prompt():
  result=b''
  while b'(qemu)' not in result:
   data=monitor.recv(4096)
   if not data:raise EOFError('Monitor closed')
   result+=data
  return result
 prompt();monitor.sendall(('screendump "'+str(target)+'"\n').encode());result=prompt()
 if not target.is_file():raise RuntimeError(result.decode(errors='replace'))
try:
 from PIL import Image
 Image.open(target).save(target.with_suffix('.png'))
except ImportError:pass
print(target)
