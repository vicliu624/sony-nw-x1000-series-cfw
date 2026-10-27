"""Select isolated, project-owned inputs and outputs for actual-ELF workflows."""
from pathlib import Path
import hashlib,json,os,re

def _profile():
 value=os.environ.get('HB_WORKFLOW_PROFILE')
 if value is not None:assert re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',value)
 return value

def composition_path(root):
 root=Path(root).resolve();path=(root/os.environ.get('HB_WORKFLOW_COMPOSITION','work/libc-product-review-0.1.0-dev.16-r3')).resolve()
 assert path.is_relative_to(root/'work') and path!=root/'work'
 return path

def work_area(root,name):
 assert re.fullmatch(r'[a-z0-9-]+',name)
 root=Path(root).resolve();profile=_profile();base=root/'work'
 if profile:base=base/'workflow-profiles'/profile
 path=base/name;path.mkdir(parents=True,exist_ok=True);return path

def evidence_path(root,name):
 assert re.fullmatch(r'[a-z0-9-]+\.json',name)
 root=Path(root).resolve();profile=_profile();base=root/'sources'
 if profile:base=base/'workflow-profiles'/profile
 base.mkdir(parents=True,exist_ok=True);return base/name

def stamp_report(root,report):
 root=Path(root).resolve();helper=Path(__file__).resolve()
 report.setdefault('source_hashes',{})[str(helper.relative_to(root))]=hashlib.sha256(helper.read_bytes()).hexdigest()
 report['workflow_profile']=_profile() or 'r3'
 report['composition']=str(composition_path(root).relative_to(root))
 return report

def write_report(root,name,report):
 evidence_path(root,name).write_text(json.dumps(stamp_report(root,report),indent=2)+'\n')
