"""Index stock script references to network debug configuration, offline only."""
from pathlib import Path
import gzip,hashlib,io,json,tarfile
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
needles=('netconfig','netstart','wlan_load_driver');texts=[];links=[];count=0;binary_refs=[]
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)),mode='r:') as tar:
 for member in tar:
  if member.issym() and any(n in member.linkname for n in needles):links.append({'path':member.name,'target':member.linkname})
  if not member.isfile():continue
  data=tar.extractfile(member).read();count+=1
  if not any(n.encode() in data for n in needles):continue
  if b'\0' in data:
   binary_refs.append({'path':member.name,'sha256':hashlib.sha256(data).hexdigest(),'matched_strings':[n for n in needles if n.encode() in data]});continue
  lines=data.decode('utf-8',errors='replace').splitlines()
  texts.append({'path':member.name,'sha256':hashlib.sha256(data).hexdigest(),'lines':[{'line':i+1,'text':line} for i,line in enumerate(lines) if any(n in line for n in needles)]})
report={'rootfs_sha256':sha,'regular_files_scanned':count,'text_references':texts,'binary_string_references':binary_refs,'symlink_references':links,'all_passed':True,'physical_device_access':False,'limits':['Text and byte-name reference inventory only; dynamic construction and indirect calls are not excluded.','Scripts are read as data, never executed; presence does not prove actual boot conditions.','Binary matches require instruction-level follow-up, not a claim that the named path is executed.']}
(ROOT/'sources/stock-network-config-references.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
