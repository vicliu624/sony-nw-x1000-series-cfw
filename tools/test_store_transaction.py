"""Build/test C store transaction core on host; build an unlinked ARM object only."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-tests';work.mkdir(exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();manifest=ROOT/'work'/('integration-'+version)/'manifest.json'
protected=[ROOT/'VERSION',manifest]+[manifest.parent/row['path'] for row in json.loads(manifest.read_text())['files']]
def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=hashes()
source=['runtime/store/transaction.c','tools/test_store_transaction.c']
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*source,'-o',str(work/'transaction-test')],cwd=ROOT,check=True)
result=subprocess.run([str(work/'transaction-test')],cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
count=int(re.search(r'(\d+) cases passed',result.stdout)[1]);assert count==24
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',source[0],'-o',str(work/'transaction.arm.o')],cwd=ROOT,check=True)
assert before==hashes()
report={'all_passed':True,'physical_device_access':False,'model_cases':count,'C_core_sha256':hashlib.sha256((ROOT/source[0]).read_bytes()).hexdigest(),'ARM_object_sha256':hashlib.sha256((work/'transaction.arm.o').read_bytes()).hexdigest(),'candidate_version':version,'candidate_unchanged':True,'filesystem_backend_implemented':False,'store_application_implemented':False,'limits':['In-memory backend with atomic/no-effect failing operations, not actual FAT or power-loss tests.','ARM object compile only, no linked app or device execution.','Inspection/space/integrity/cancellation and storage confinement depend on the future filesystem adapter.','Does not add installer code to the current integration candidate.']}
(ROOT/'sources/native-store-transaction-core.json').write_text(json.dumps(report,indent=2)+'\n');print(result.stdout.strip());print(json.dumps(report,indent=2))
