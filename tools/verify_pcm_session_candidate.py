"""Independent candidate9 tar/metadata/byte check; no player or updater execution."""
from pathlib import Path
import sys,io,json,hashlib,struct,tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
version=(ROOT/'VERSION').read_text().strip();d=ROOT/'dist'/version;candidate=d/'diagnostic-review-9';base=d/'diagnostic-review-8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for folder in [candidate,d/'first-device-test-candidate9']:
 seen=set()
 for line in (folder/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split('  ',1);assert name not in seen and '..'not in Path(name).parts and not name.startswith('/');seen.add(name);assert sha(folder/name)==digest,name
 assert seen=={str(p.relative_to(folder)).replace('\\','/')for p in folder.rglob('*')if p.is_file()and p.name!='SHA256SUMS'}
_,old=unpack((base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes(),require_stock=False);_,new=unpack((candidate/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes(),require_stock=False);assert new[:3]==old[:3]
changes=[]
with tarfile.open(fileobj=io.BytesIO(old[3]),mode='r:gz')as a,tarfile.open(fileobj=io.BytesIO(new[3]),mode='r:gz')as b:
 ma=a.getmembers();mb=b.getmembers();assert len(ma)==len(mb)==1433
 for x,y in zip(ma,mb):
  for field in ['name','mode','uid','gid','size','mtime','type','linkname','uname','gname','devmajor','devminor','pax_headers']:assert getattr(x,field)==getattr(y,field),(x.name,field)
  if x.isfile():
   before=a.extractfile(x).read();after=b.extractfile(y).read()
   if before!=after:
    assert x.name.removeprefix('./')=='usr/local/bin/SpiderApp';offsets=[i for i,(v,w)in enumerate(zip(before,after))if v!=w];assert offsets==[0x4ce1c0];assert struct.unpack_from('<I',before,offsets[0])[0]==0xe3a03000 and struct.unpack_from('<I',after,offsets[0])[0]==0xe3a03001;changes.append(x.name)
 assert len(changes)==1
kit=d/'first-device-test-candidate9';assert (kit/'01_PC_UPDATE/NW_WM_FW.UPG').read_bytes()==(candidate/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes()
assert sha(kit/'01_PC_UPDATE/FWUpdater.exe')=='3cf7eb2e354d2e6d3f0cddd06ab67755696579a0d2cc85b68672ecc44ccb3c1c'
assert sha(kit/'01_PC_UPDATE/NW-X10X0.ini')=='ff3d772ab446b3749272bf57b1c31b17765d4a807ff896de8b46f9bbb6dc11fa'
report={'passed':True,'root_entries':1433,'changed_files':changes,'byte_differences':1,'all_metadata_and_sizes_preserved':True,'first_three_components_identical':True,'upg_sha256':sha(kit/'01_PC_UPDATE/NW_WM_FW.UPG'),'original_updater_ini_verified':True,'hardware_tested':False}
(ROOT/'work/candidate9-build/independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
