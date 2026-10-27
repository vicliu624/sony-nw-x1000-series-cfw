"""External STX package metadata and validation; no firmware mutation."""
import hashlib,re,struct,json
from pathlib import Path
REQUIRED_IDS=json.loads((Path(__file__).resolve().parents[1]/"assets/language/required-ids.json").read_text())["required_ids"]
from resources import parse_stx
TARGET='sony-nw-x1000-jp-1.11'
ABI='stx7310-hb-v1'
PARAMETERS=json.loads((Path(__file__).resolve().parents[1]/'assets/language/parameter-counts.json').read_text())['counts']
BASE_LANGUAGES={'de':0,'en':1,'es':2,'fr':3,'it':4,'pt':5,'ru':6,'jp':7,'kr':8,'cs':9,'ct':10}
ID=re.compile(r'[A-Za-z0-9][A-Za-z0-9-]{0,31}\Z')
FIELDS={'api','target','resource_abi','id','name','base_language','wording','wording_bytes','wording_sha256'}
def validate_id(value):
 if not isinstance(value,str)or not ID.fullmatch(value)or value.lower()=='stock':raise ValueError('Invalid or reserved language ID')
 return value

def validate_wording(data,base_language=None):
 if not 56<=len(data)<=2097152 or len(data)%2:raise ValueError('Bad STX size')
 if struct.unpack_from('<I',data,52)[0]!=len(data):raise ValueError('Bad mapped length')
 texts=parse_stx(data)
 if len(texts)!=7310:raise ValueError('Incompatible wording ABI')
 if any(not texts[i]for i in REQUIRED_IDS):raise ValueError('Required interface text is missing')
 if any(len(s.encode('utf-8'))>330 or len(s.encode('utf-16-le'))//2>328 for s in texts):raise ValueError('Text exceeds observed original resource length bounds')
 if sum(len(s.encode('utf-16-le'))+2 for s in texts if s)>len(data)*4:raise ValueError('Excessive shared-string scanning')
 if base_language is not None and base_language not in BASE_LANGUAGES:raise ValueError('Unknown base language')
 for i,text in enumerate(texts):
  counts=PARAMETERS.get(str(i));n=text.count('\ue42a')
  allowed={0}if counts is None else{counts[base_language]}if base_language is not None else set(counts.values())
  if n not in allowed:raise ValueError('Dynamic parameter arity mismatch at '+str(i))
 return texts

def manifest(package_id,name,base_language,data=None):
 validate_id(package_id)
 if base_language not in BASE_LANGUAGES:raise ValueError('Unsupported base/font mapping')
 if not isinstance(name,str)or not 1<=len(name)<=32 or any(ord(c)<32 or ord(c)>126 or c=='='for c in name):raise ValueError('Invalid display name')
 if data is not None:validate_wording(data,base_language)
 values={'api':'1','target':TARGET,'resource_abi':ABI,'id':package_id,'name':name,'base_language':base_language,'wording':'stock'if data is None else 'wording.stx','wording_bytes':'0'if data is None else str(len(data)),'wording_sha256':'none'if data is None else hashlib.sha256(data).hexdigest()}
 return ''.join(k+'='+v+'\n'for k,v in values.items()).encode('ascii')

def parse_manifest(raw,wording=None):
 if len(raw)>1024 or b'\0'in raw:raise ValueError('Bad manifest size')
 try:text=raw.decode('ascii')
 except UnicodeError as e:raise ValueError('Manifest must be ASCII')from e
 values={}
 for line in text.splitlines():
  if not line or '='not in line:raise ValueError('Malformed manifest')
  key,value=line.split('=',1)
  if key in values:raise ValueError('Duplicate manifest key')
  values[key]=value
 if set(values)!=FIELDS or values['api']!='1'or values['target']!=TARGET or values['resource_abi']!=ABI:raise ValueError('Unsupported manifest ABI')
 if values['wording']not in ('stock','wording.stx'):raise ValueError('Arbitrary resource paths forbidden')
 if values['wording']=='stock':
  if wording is not None or values['wording_bytes']!='0'or values['wording_sha256']!='none':raise ValueError('Bad stock reference')
 else:
  if wording is None:raise ValueError('Resource missing')
  validate_wording(wording)
  if values['wording_bytes']!=str(len(wording))or values['wording_sha256']!=hashlib.sha256(wording).hexdigest():raise ValueError('Resource identity mismatch')
 # Canonical reconstruction also checks ID/name/base mapping.
 manifest(values['id'],values['name'],values['base_language'],wording)
 return values
