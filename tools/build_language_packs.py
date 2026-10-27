"""Build external data-only language packs. Never modify a firmware/rootfs."""
from pathlib import Path
import argparse,json,hashlib,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from language_pack import manifest,parse_manifest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--id',required=True);p.add_argument('--name',required=True);p.add_argument('--base-language',required=True);p.add_argument('--wording',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
out=(ROOT/a.output).resolve()
if not any(out.is_relative_to(ROOT/part)for part in ('dist','work'))or out in (ROOT/'dist',ROOT/'work'):raise ValueError('Output must be a new subdirectory of project dist/ or work/')
if out.exists():raise FileExistsError('Preserve previous pack output')
data=a.wording.read_bytes()if a.wording else None;metadata=manifest(a.id,a.name,a.base_language,data);parse_manifest(metadata,data)
folder=out/'HOMEBREW/languages'/a.id;folder.mkdir(parents=True);(folder/'language.ini').write_bytes(metadata)
if data is not None:(folder/'wording.stx').write_bytes(data)
report={'passed':True,'id':a.id,'base_language':a.base_language,'kind':'stock-reference'if data is None else 'external-STX','resource_bytes':0 if data is None else len(data),'system_partition_bytes':0,'firmware_changed':False,'requires_generic_external_loader':True,'compatible_with_candidate10':False,'metadata_sha256':hashlib.sha256(metadata).hexdigest(),'resource_sha256':None if data is None else hashlib.sha256(data).hexdigest(),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [Path(__file__),ROOT/'scripts/language_pack.py',ROOT/'scripts/resources.py',ROOT/'assets/language/required-ids.json',ROOT/'assets/language/parameter-counts.json']}}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'README.md').write_text((ROOT/'docs/LOCALIZATION.md').read_text(encoding='utf-8'),encoding='utf-8')
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
z=out.with_suffix('.zip')
if z.exists():raise FileExistsError(z)
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED)as archive:
 for f in sorted(out.rglob('*')):
  if f.is_file():archive.write(f,f.relative_to(out).as_posix())
with zipfile.ZipFile(z)as archive:
 assert archive.testzip()is None
 for f in out.rglob('*'):
  if f.is_file():assert archive.read(f.relative_to(out).as_posix())==f.read_bytes()
print(json.dumps({**report,'zip':str(z)},indent=2))
