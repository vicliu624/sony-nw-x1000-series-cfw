"""Evidence verifier regression: failed/stale/mismatched reports must reject."""
from pathlib import Path
import tempfile,json,hashlib,copy
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/evidence-check-tests';work.mkdir(exist_ok=True)
rows=[]
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
 root=Path(temp)
 for name,data in [('source.c',b'source'),('generator.py',b'generator'),('app',b'ELF fixture') ]:(root/name).write_bytes(data)
 sha=lambda p:hashlib.sha256((root/p).read_bytes()).hexdigest()
 original={'all_bounded_checks_passed':True,'source_hashes':{'source.c':sha('source.c')},'generator_source':'generator.py','generator_sha256':sha('generator.py'),'artifact':'app','bytes':11,'sha256':sha('app')}
 def check(name,report,accept):
  (root/'report.json').write_text(json.dumps(report))
  try:verify_report(root,'report.json');result=True
  except (ValueError,OSError):result=False
  assert result==accept,name
  rows.append({'case':name,'accepted':result})
 check('current report',original,True)
 for name,key,value in [('failed pass flag','all_bounded_checks_passed',False),('truthy numeric pass flag','all_bounded_checks_passed',1),('stale source','source_hashes',{'source.c':'0'*64}),('missing source','source_hashes',{'missing.c':'0'*64}),('outside source','source_hashes',{'../outside.c':'0'*64}),('stale generator','generator_sha256','0'*64),('artifact length mismatch','bytes',12),('artifact digest mismatch','sha256','0'*64)]:
  report=copy.deepcopy(original);report[key]=value;check(name,report,False)
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{'tools/evidence_checks.py':hashlib.sha256((ROOT/'tools/evidence_checks.py').read_bytes()).hexdigest()},'limits':['Host report validation only; not test reexecution or hardware qualification.']}
(ROOT/'sources/evidence-check-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Evidence verifier: current accepted; eight invalid/stale report cases rejected.')
