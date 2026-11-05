"""Freeze private first-use external files; never connects to or writes a device."""
import argparse,json,shutil,time
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--component-review',required=True)
 parser.add_argument('--pairing-review',required=True)
 args=parser.parse_args()
 cp=private(args.component_review);component=json.loads(cp.read_text())
 pp=private(args.pairing_review);pair=json.loads(pp.read_text())
 if not component['passed'] or component['configuration_kind']!='unqualified-private' or not pair['prepared'] or pair['installed']:raise ValueError('Expected current private uninstalled pairing')
 # Recheck current source closures, not merely the old aggregate pass.
 for row in component['receipts'].values():
  path,_=receipt(row['local'])
  if digest(path)!=row['sha256']:raise ValueError('Component receipt changed')
 pnpath=private(pp.parent/'first-use-pn-proposal/review.private.json');pn=json.loads(pnpath.read_text())
 if pn['pairing_review_sha256']!=digest(pp) or pn['keys_sha256']!=pair['files']['session.keys']['sha256']:raise ValueError('PN proposal pairing mismatch')
 sources={}
 for name in ('service','owner','configuration'):
  row=component['components'][name];leaf={'service':'service.arm','owner':'owner.arm','configuration':'config.bin'}[name]
  sources['runtime/'+leaf]=(private(row['local']),row)
 if digest(sources['runtime/config.bin'][0])!=pair['files']['config.bin']['sha256']:raise ValueError('Supervisor pairing differs')
 sources['session.keys']=(private(pp.parent/'session.keys'),pair['files']['session.keys'])
 for name,row in pn['files'].items():sources['pn/'+name]=(private(pnpath.parent/name),row)
 for row in component['radio_dependencies']['immutable_inputs']:
  name=row['device_path'].rsplit('/',1)[-1]
  sources['candidate/'+name]=(private(ROOT/'work/espnow-full-radio-review-3/candidate'/name),row)
 if len(sources)!=8:raise ValueError('Incomplete first-use set')
 for path,row in sources.values():
  if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('First-use input identity mismatch')
 out=ROOT/'work/remote-first-use'/str(time.time_ns());out.mkdir(parents=True)
 files=[]
 for name,(path,row) in sources.items():
  target=out/'files'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
  if digest(target)!=row['sha256']:raise ValueError('Staging copy mismatch')
  files.append(dict(relative=name,bytes=row['bytes'],sha256=row['sha256']))
 report=dict(schema='x1000-remote-first-use-v1',prepared=True,installed=False,device_accessed=False,
  files=files,total_bytes=sum(row['bytes'] for row in files),target_directory='HOMEBREW/data/wireless-remote',
  component_review=cp.relative_to(ROOT).as_posix(),component_sha256=digest(cp),pairing_review_sha256=digest(pp),
  limits=['Private first-use files only; not a firmware or authorization to install.',
   'Existing destination refuses; never restore zero PN records after use.',
   'Installation requires current Sony USB identity and a separate manual operation.'])
 (out/'plan.private.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,directory=out.relative_to(ROOT).as_posix(),files=len(files),total_bytes=report['total_bytes'],installed=False,secrets_printed=False),indent=2))
if __name__=='__main__':main()
