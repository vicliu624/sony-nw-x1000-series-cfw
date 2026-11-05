"""Prepare private matching player/MCU pairing files; no serial, network or device I/O."""
import argparse,hashlib,json,re,secrets,struct,time
from pathlib import Path
from app_registry import ROOT

def address(value):
 value=value.replace(':','').replace('-','')
 if not re.fullmatch('[0-9a-fA-F]{12}',value):raise ValueError('Expected a six-byte MAC address')
 result=bytes.fromhex(value)
 if not any(result) or result[0]&1:raise ValueError('Expected a nonzero unicast address')
 return result

def prepare(player,remote,generation,mode_enabled=False):
 if player==remote or len(player)!=6 or len(remote)!=6 or not 0<generation<2**64:raise ValueError('Distinct player/controller addresses and nonzero uint64 generation required')
 session=secrets.randbits(64) or 1
 auth=secrets.token_bytes(32);pmk=secrets.token_bytes(16);api_lmk=secrets.token_bytes(16);cookie=secrets.token_bytes(16)
 # Application authentication and encrypted transport use distinct keys.
 config=(b'XWRUN002' if mode_enabled else b'XWRUN001')+struct.pack('<QQ',generation,session)+remote+b'\0\0'+auth+cookie
 line='pair '+' '.join((player.hex(),f'{session:016x}',auth.hex(),api_lmk.hex(),pmk.hex()))+'\n'
 if len(config)!=80 or len(line.rstrip('\n'))!=165:raise ValueError('Pairing wire size mismatch')
 return config,pmk+api_lmk,line.encode('ascii')

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--player-mac',required=True,type=address)
 parser.add_argument('--remote-mac',required=True,type=address)
 parser.add_argument('--generation',type=int,default=1)
 parser.add_argument('--host-review',type=Path,help='Enable five-mode protocol only with a fresh compatible native host review')
 args=parser.parse_args()
 host_path=None
 if args.host_review:
  from remote_host_review import mode_host
  host_path,host=mode_host(args.host_review)
 config,keys,line=prepare(args.player_mac,args.remote_mac,args.generation,host_path is not None)
 out=ROOT/'work/remote-pairing'/str(time.time_ns());out.mkdir(parents=True)
 for name,data in [('config.bin',config),('session.keys',keys),('controller-usb.private.txt',line)]:
  path=out/name;path.write_bytes(data);path.chmod(0o600)
 report=dict(prepared=True,device_accessed=False,installed=False,hardware_qualified=False,
  player_mac=args.player_mac.hex(),remote_mac=args.remote_mac.hex(),generation=args.generation,
  protocol=config[:8].decode(),play_mode_enabled=host_path is not None,
  host_review=host_path.relative_to(ROOT).as_posix() if host_path else None,
  host_review_sha256=hashlib.sha256(host_path.read_bytes()).hexdigest() if host_path else None,
  files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in [('config.bin',config),('session.keys',keys),('controller-usb.private.txt',line)]},
  pn_records_generated=False,existing_keys_replaced=False,
  limits=['Fresh private pairing proposal; never overwrite existing pairing or packet-number journals automatically.',
   'Controller command contains secrets; do not print, commit or send through logs.',
   'Five-mode protocol requires separate matching host review before XWRUN002 is enabled.',
   'Filesystem mode bits do not replace Windows directory access controls.'])
 (out/'review.private.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,directory=out.relative_to(ROOT).as_posix(),installed=False,secrets_printed=False),indent=2))
if __name__=='__main__':main()
