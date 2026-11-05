"""Prepare first-use counters for a fresh private pairing; never installs or resets them."""
import argparse,hashlib,json,struct
from Crypto.Cipher import AES
from review_managed_remote_profile import private,digest
from prepare_remote_pairing import address

def records(player,remote,keys):
 if len(keys)!=32:raise ValueError('Expected PMK16 plus API-LMK16')
 wire=AES.new(keys[:16],AES.MODE_ECB).encrypt(keys[16:])
 scopes=[hashlib.sha256(b'X1000-CCMP-TX-PN-v1'+player+wire).digest(),
         hashlib.sha256(b'X1000-CCMP-RX-PN-v1'+player+remote+wire).digest()]
 result={}
 for scope in scopes:
  prefix=b'XPN00001'+scope+struct.pack('<Q',0)
  result['pn-'+scope.hex()+'.dat']=prefix+hashlib.sha256(prefix).digest()
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pairing-review',required=True)
 args=parser.parse_args();path=private(args.pairing_review);review=json.loads(path.read_text())
 if not review.get('prepared') or review.get('installed') is not False or review.get('existing_keys_replaced') is not False:raise ValueError('Expected unused fresh-pairing proposal')
 keypath=private(path.parent/'session.keys')
 if digest(keypath)!=review['files']['session.keys']['sha256']:raise ValueError('Pairing key identity mismatch')
 items=records(address(review['player_mac']),address(review['remote_mac']),keypath.read_bytes())
 # One-use staging marker. Never remove/recreate this directory to reuse a key.
 out=path.parent/'first-use-pn-proposal';out.mkdir(exist_ok=False)
 for name,data in items.items():
  with (out/name).open('xb') as stream:stream.write(data)
 report=dict(prepared=True,first_use_only=True,installed=False,device_accessed=False,
  pairing_review_sha256=digest(path),keys_sha256=digest(keypath),
  files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in items.items()},
  overwrite_permitted=False,repeat_install_permitted=False,
  limits=['Only for a fresh unused pairing. A copied or used key must never receive these zero counters.',
   'Installation must create missing scope files exclusively; never merge by overwriting existing records.',
   'Power loss or uncertain installation must be reviewed; do not retry by restoring seed records.',
   'This PC staging output does not prove device mount/USB ownership or actual radio operation.'])
 (out/'review.private.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,record_count=len(items),installed=False,secrets_printed=False),indent=2))
if __name__=='__main__':main()
