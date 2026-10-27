"""Inject a parser-list fault only in a PC child to test failure audit capture."""
from pathlib import Path
import json,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'work/compact-verifier-audit-test-1';out.mkdir(exist_ok=False)
report=out/'injected-failure-audit.json';candidate=ROOT/'dist/0.1.0-dev.16/diagnostic-review-5';upg=candidate/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';before=hashlib.sha256(upg.read_bytes()).hexdigest()
code='''import tarfile,sys,runpy
original=tarfile.TarFile.getmembers
def injected(self):
 items=original(self)
 if len(items)==1433 and items[-1].name.endswith('ucs2-dev-sid-999-99.swd'):return items[:-1]
 return items
tarfile.TarFile.getmembers=injected
sys.argv=['verify_compact_feedback_diagnostic.py',sys.argv[1],'--report',sys.argv[2]]
runpy.run_path('tools/verify_compact_feedback_diagnostic.py',run_name='__main__')
'''
run=subprocess.run(['.venv/bin/python','-c',code,str(candidate.relative_to(ROOT)),str(report.relative_to(ROOT))],cwd=ROOT,capture_output=True,text=True)
(out/'stdout.txt').write_text(run.stdout);(out/'stderr.txt').write_text(run.stderr)
assert run.returncode!=0 and report.is_file()
j=json.loads(report.read_text());assert j['passed'] is False and j['failure']['type']=='AssertionError' and j['stages']['archive_counts']=={'candidate':1432,'original':1432,'candidate_unique':1432,'duplicate_names':{}}
assert j['stages']['candidate_snapshot']['sha256']==before and hashlib.sha256(upg.read_bytes()).hexdigest()==before
result={'passed':True,'fault':'Child-only getmembers return list loses one new entry; no package or filesystem data changed','failure_rejected':True,'failure_audit_saved':True,'counts_captured':j['stages']['archive_counts'],'candidate_unchanged':True,'candidate_sha256':before,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'test-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
