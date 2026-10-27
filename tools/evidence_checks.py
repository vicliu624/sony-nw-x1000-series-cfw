"""Bound saved evidence to current source/artifact bytes; no device qualification."""
from pathlib import Path
import hashlib,json

def _file(root,relative):
 path=(root/relative).resolve()
 if not path.is_relative_to(root.resolve()) or not path.is_file():raise ValueError('Missing/outside evidence file: '+str(relative))
 return path

def verify_report(root,relative):
 root=Path(root);report=json.loads(_file(root,relative).read_text())
 if not isinstance(report,dict):raise ValueError('Evidence must be an object: '+relative)
 for field in ('all_bounded_checks_passed','all_passed'):
  if field in report and report[field] is not True:raise ValueError('Failed evidence: '+relative+' '+field)
 for field in ('source_hashes','full_source_hashes','platform_source_hashes'):
  if field not in report:continue
  if not isinstance(report[field],dict):raise ValueError('Invalid source map: '+relative)
  for source,digest in report[field].items():
   if hashlib.sha256(_file(root,source).read_bytes()).hexdigest()!=digest:raise ValueError('Stale source evidence: '+relative+' '+source)
 if 'generator_source' in report:
  if hashlib.sha256(_file(root,report['generator_source']).read_bytes()).hexdigest()!=report.get('generator_sha256'):raise ValueError('Stale generator: '+relative)
 if isinstance(report.get('artifact'),str) and isinstance(report.get('sha256'),str) and isinstance(report.get('bytes'),int):
  payload=_file(root,report['artifact']).read_bytes()
  if len(payload)!=report['bytes'] or hashlib.sha256(payload).hexdigest()!=report['sha256']:raise ValueError('Artifact mismatch: '+relative)
 return report
