"""Inspect validity metadata of stock CA certificates; no trust or network tests."""
from pathlib import Path
import base64,gzip,hashlib,io,json,re,tarfile
from datetime import datetime,timezone
from Crypto.Util.asn1 import DerSequence,DerObject
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)),mode='r:') as tar:data=tar.extractfile('./etc/pki/tls/certs/ca-bundle.crt').read()
inventory=json.loads((ROOT/'sources/stock-tls-inventory.json').read_text())
assert inventory['all_passed'] and inventory['stock_CA_bundle']['sha256']==hashlib.sha256(data).hexdigest()
asof=datetime(2026,10,24,tzinfo=timezone.utc);rows=[]
def date(encoded):
 obj=DerObject().decode(encoded);value=obj.payload.decode('ascii')
 if encoded[0]==0x17:
  year=int(value[:2]);value=str(1900+year if year>=50 else 2000+year)+value[2:]
 else:assert encoded[0]==0x18
 return datetime.strptime(value,'%Y%m%d%H%M%SZ').replace(tzinfo=timezone.utc)
for pem in re.findall(rb'-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----',data,re.S):
 der=base64.b64decode(pem);certificate=DerSequence().decode(der);tbs=DerSequence().decode(certificate[0])
 version_present=isinstance(tbs[0],bytes) and tbs[0][0]==0xa0
 validity=DerSequence().decode(tbs[4 if version_present else 3]);start,end=map(date,validity)
 status='not-yet-valid' if asof<start else 'expired' if asof>end else 'within-validity'
 rows.append({'certificate_sha256':hashlib.sha256(der).hexdigest(),'not_before':start.isoformat(),'not_after':end.isoformat(),'date_status':status})
assert rows
report={'as_of_utc':asof.isoformat(),'bundle_sha256':hashlib.sha256(data).hexdigest(),'certificate_count':len(rows),'counts':{s:sum(r['date_status']==s for r in rows) for s in ('within-validity','expired','not-yet-valid')},'all_passed':True,'physical_device_access':False,'certificates':rows,'limits':['ASN.1 validity metadata only; no certificate signature, hostname, chain or server verification.','Trust-anchor expiry handling can differ from leaf/intermediate checks; counts alone do not predict which HTTPS connections succeed.','Does not read the device clock or any device-side trust modifications.']}
(ROOT/'sources/stock-ca-validity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='certificates'},indent=2))
