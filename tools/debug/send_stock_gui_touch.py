"""Send bounded touch input only to the verified local QEMU session's UART."""
import argparse,json,socket,struct,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--session',required=True);p.add_argument('--tap',nargs=2,type=int,required=True)
p.add_argument('--hold-ms',type=int,default=160);args=p.parse_args()
session=(ROOT/args.session).resolve();assert session.is_relative_to(ROOT/'work')
launch=json.loads((session/'launch.json').read_text());assert launch['physical_device_access'] is False
pid=launch['qemu_pid'];actual=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
command=[v.encode() for v in launch['command']]
assert actual[:-1]==command and 'qemu-system-arm' in launch['command'][0]
x,y=args.tap;assert 0<=x<240 and 0<=y<432 and 30<=args.hold_ms<=2000
assert type(launch['touch_port']) is int and 1024<=launch['touch_port']<=65535
with socket.create_connection(('127.0.0.1',launch['touch_port']),timeout=2) as channel:
 channel.sendall(struct.pack('<4sHHB',b'XWT1',x,y,1));time.sleep(args.hold_ms/1000)
 channel.sendall(struct.pack('<4sHHB',b'XWT1',x,y,0));time.sleep(.1)
print(json.dumps(dict(qemu_pid=pid,tap=[x,y],hold_ms=args.hold_ms,physical_device_access=False)))
