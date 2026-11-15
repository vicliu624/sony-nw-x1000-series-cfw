"""Build/test C store transaction core on host; build an unlinked ARM object only."""
from pathlib import Path
import hashlib,json,re,subprocess
from store_test_fixture import ROOT, workspace

scratch = workspace('store-transaction-')
work = Path(scratch.name)
source=['runtime/store/transaction.c','tools/test_store_transaction.c']
subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror',*source,'-o',str(work/'transaction-test')],cwd=ROOT,check=True)
result=subprocess.run([str(work/'transaction-test')],cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
count=int(re.search(r'(\d+) cases passed',result.stdout)[1]);assert count==24
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-c',source[0],'-o',str(work/'transaction.arm.o')],cwd=ROOT,check=True)
report={'all_passed':True,'physical_device_access':False,'model_cases':count,'C_core_sha256':hashlib.sha256((ROOT/source[0]).read_bytes()).hexdigest(),'ARM_object_sha256':hashlib.sha256((work/'transaction.arm.o').read_bytes()).hexdigest(),'limits':['In-memory backend with atomic/no-effect failing operations, not actual FAT or power-loss tests.','ARM object compile only, no linked app or device execution.','Inspection/space/integrity/cancellation and storage confinement depend on the future filesystem adapter.']}
report['source_hashes'] = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in (*source, 'tools/store_test_fixture.py', 'tools/test_store_transaction.py')
}
print(json.dumps(report, indent=2))
