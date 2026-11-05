"""Host ASan/UBSan fork/exec/FD/log tests; ARM supervisor chain is separate."""
import hashlib,json,subprocess,time
from app_registry import ROOT
out=ROOT/'work/supervisor-process-tests'/str(time.time_ns());out.mkdir(parents=True)
child=out/'child';host=out/'parent'
child_source='tools/fixtures/supervisor_process_child.c'
sources=['runtime/apps/wireless-remote/supervisor_process.c','tools/test_supervisor_process.c']
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror',child_source,'-o',str(child)],cwd=ROOT,check=True)
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',
                '-DWR_SUPERVISOR_PATH="'+str(child)+'"',*sources,'-o',str(host)],cwd=ROOT,check=True)
result=subprocess.run([str(host)],capture_output=True,text=True,timeout=30)
assert result.returncode==0 and 'SUPERVISOR_PROCESS_PASS' in result.stdout,result.stdout+result.stderr
report=dict(passed=True,device_accessed=False,host_sanitizers=True,actual_fork_exec_wait=True,
            child_modeled=True,hardware_qualified=False,
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,child_source,
            'runtime/apps/wireless-remote/supervisor_process.h','tools/test_supervisor_process.py']},
            limits=['Host process/descriptor behavior only; Sony loader/ARM chain is checked separately.',
                    'No native threaded SpiderApp atfork/touch timing, RF or admission qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
