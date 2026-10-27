"""Guard that language-package development cannot grow or modify system resources."""
import io,tarfile
FIELDS=('mode','uid','gid','mtime','type','linkname','uname','gname','size','devmajor','devminor','pax_headers')
def audit_minimal_overlay(base_root_gzip,candidate_root_gzip):
 with tarfile.open(fileobj=io.BytesIO(base_root_gzip),mode='r:gz')as a,tarfile.open(fileobj=io.BytesIO(candidate_root_gzip),mode='r:gz')as b:
  left=a.getmembers();right=b.getmembers()
  if len(left)!=len(right)or len({m.name for m in left})!=len(left)or len({m.name for m in right})!=len(right):raise ValueError('New/deleted/duplicate system entries')
  changes=[];resources=[]
  for x,y in zip(left,right):
   if x.name!=y.name:raise ValueError('System path/order changed')
   if any(getattr(x,k)!=getattr(y,k)for k in FIELDS):raise ValueError('System metadata or file size changed: '+x.name)
   if x.isfile():
    name=x.name.removeprefix('./');different=a.extractfile(x).read()!=b.extractfile(y).read()
    if different and name!='usr/local/bin/SpiderApp':raise ValueError('External language resource embedded or unrelated system file modified: '+name)
    if different:changes.append(name)
    if name.startswith(('usr/local/share/gemini/res/','usr/local/share/GUI/')):resources.append(name)
 return {'passed':True,'system_logical_growth_from_baseline_bytes':0,'modified_system_files':changes,'unchanged_system_resource_files':resources,'new_system_entries':0}
