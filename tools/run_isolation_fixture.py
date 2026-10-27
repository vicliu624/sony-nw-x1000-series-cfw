"""Run trusted host-only probes in a disposable private mount namespace.
Run in WSL as root. No Sony program or physical device is executed/accessed.
"""
import hashlib
import json
import os
import resource
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    if os.name!="posix" or os.geteuid()!=0:raise SystemExit("Run on Linux as root for the disposable fixture only")
    os.chdir(ROOT)
    for source,out,static in [("tools/isolation_fixture.c","work/isolation-fixture",False),("tools/isolation_probe.c","work/isolation-probe",True)]:
        args=["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror"]
        if static:args.append("-static")
        subprocess.run(args+[source,"-o",out],check=True)
    fixture=ROOT/"work/isolation-fixtures"/("run-"+str(time.time_ns()));fixture.mkdir(parents=True)
    # Ensure an outside descriptor exists above 1024. It must not survive exec.
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft<4096:resource.setrlimit(resource.RLIMIT_NOFILE,(4096,hard))
    fd=os.open(ROOT/"README.md",os.O_RDONLY);os.dup2(fd,2048);os.close(fd)
    try:
        run=subprocess.run([str(ROOT/"work/isolation-fixture"),"--host-fixture",str(fixture),str(ROOT/"work/isolation-probe")],text=True,capture_output=True,timeout=20,pass_fds=(2048,))
    finally:os.close(2048)
    lines=run.stdout.splitlines()
    passed=[line[5:]for line in lines if line.startswith("PASS ")]
    assert run.returncode==0 and len(passed)==14 and not any(line.startswith("FAIL ")for line in lines),(run.returncode,run.stdout,run.stderr)
    assert not list(fixture.iterdir()),"Fixture mount leaked into parent namespace"
    assert str(fixture) not in Path("/proc/self/mountinfo").read_text(),"Mount leaked"
    result={"scope":"modern WSL Linux host only; not Sony kernel or device qualification","checks":passed,"passed":14,"real_device_nodes_exposed":False,"private_namespace_cleaned":True,"probe_sha256":hashlib.sha256((ROOT/"work/isolation-probe").read_bytes()).hexdigest(),"firmware_generated":False}
    (ROOT/"work/isolation-audit/host-fixture-result.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
