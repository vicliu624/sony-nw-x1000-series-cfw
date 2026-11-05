"""Decode a copied parent-process trace on the PC; no device access or success inference."""
import argparse,json,struct,zlib
from review_managed_remote_profile import private
NAMES={1:'home-entry',2:'name-query-enter',3:'name-query-return',4:'switch-enter',5:'switch-return',6:'native-prepare-enter',7:'native-prepare-decision'}
def decode(seed,data):
 if len(seed)!=2048 or len(data)!=2048:raise ValueError('Expected exact2048-byte seed and trace')
 if seed[:16]!=b'X1PARENTTRACE000' or any(seed[32:]):raise ValueError('Invalid seed format')
 if data[:32]!=seed[:32]:raise ValueError('Trace identity differs from seed')
 if any(data[1056:]):raise ValueError('Reserved tail changed')
 rows=[];invalid=[]
 for i in range(16):
  raw=data[32+i*64:96+i*64]
  if not any(raw):continue
  reason=None
  if raw[:4]!=b'HBP1':reason='record-magic'
  elif struct.unpack_from('<I',raw,4)[0]!=i+1:reason='slot-stage-mismatch'
  elif not 1<=struct.unpack_from('<I',raw,8)[0]<=16:reason='sequence-range'
  elif zlib.crc32(raw[:60])!=struct.unpack_from('<I',raw,60)[0]:reason='crc32'
  if reason:invalid.append(dict(slot=i+1,reason=reason));continue
  words=struct.unpack('<16I',raw)
  rows.append(dict(stage=i+1,name=NAMES.get(i+1,'reserved'),sequence=words[2],payload=list(words[3:15])))
 return dict(records=rows,invalid_slots=invalid,recording_present=bool(rows),integrity_valid=not invalid,
  no_records_is_inconclusive=not rows,hardware_success_proven=False,device_accessed=False,
  limits=['Only committed records with matching identity and CRC are interpreted.','A missing record may mean no execution, refused storage, contention or an interrupted write.','Stage return does not prove an external app started or resources were safely retired.'])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seed',required=True);p.add_argument('--trace',required=True);a=p.parse_args()
 report=decode(private(a.seed).read_bytes(),private(a.trace).read_bytes());print(json.dumps(report,indent=2));return 0 if report['integrity_valid'] else 2
if __name__=='__main__':raise SystemExit(main())
