"""Real unnamed pipes/owner process, modeled radio. No device IO or deployment."""
import json
import hashlib
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import time
from app_registry import ROOT

def main():
    out=ROOT/'work/chat-owner-tests'/str(time.time_ns());out.mkdir(parents=True)
    app=out/'owner.host'
    sources=['runtime/apps/espnow-chat/chat_owner.c','tools/fixtures/chat_owner_platform.c',
        'runtime/apps/espnow-chat/chat_handoff.c','runtime/apps/espnow-chat/chat_handoff_owner.c','runtime/platform/espnow/xnow_managed_process.c',
        'tools/fixtures/xnow_control_platform.c',*[f'runtime/platform/espnow/{n}.c' for n in
        ('xnow_control','xnow_manager','xnow_session','xnow_chat')]]
    subprocess.run(['gcc','-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(ROOT/'sdk/include'),
        *sources,'-include','string.h','-o',str(app)],cwd=ROOT,check=True)
    # Reserve3/4 so child descriptor remapping has a stable inherited allowlist.
    reserved=[]
    while not reserved or reserved[-1]<5:reserved.append(os.open('/dev/null',os.O_RDONLY))
    running=[];event=struct.Struct('<IIII100s');restores={};cookie=bytes(range(1,17))
    def start():
        cr,cw=os.pipe();er,ew=os.pipe();rr,rw=os.pipe()
        def remap():os.dup2(cr,3);os.dup2(ew,4);os.dup2(rw,5)
        environment=dict(os.environ,XNOW_HANDOFF_FD='5',XNOW_HANDOFF_COOKIE=cookie.hex())
        p=subprocess.Popen([str(app),'--ipc'],pass_fds=(3,4,5,cr,ew,rw),preexec_fn=remap,env=environment,
            start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        os.close(cr);os.close(ew);os.close(rw);restores[p.pid]=rr;running.append((p,cw,er));return p,cw,er
    def restored(p,failure):
        fd=restores.pop(p.pid);record=os.read(fd,33);assert record==b'XRFDONE1'+cookie+struct.pack('<II',1,failure),record
        assert not os.read(fd,1);os.close(fd)
    def until(fd,kind,state=None):
        data=bytearray();deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            assert select.select([fd],[],[],max(0,deadline-time.monotonic()))[0],'owner event timeout'
            part=os.read(fd,event.size-len(data));assert part,'premature owner EOF';data.extend(part)
            if len(data)==event.size:
                row=event.unpack(data);data.clear()
                if row[0]==kind and (state is None or row[1]==state):return row
        raise AssertionError('expected event absent')
    try:
        first,cw,er=start();until(er,1,2)
        assert first.poll() is None and os.getpgid(first.pid)==first.pid
        duplicate,dcw,der=start();until(der,7,4);assert duplicate.wait(timeout=3)==69
        restored(duplicate,1)
        os.close(dcw);os.close(der);running.remove((duplicate,dcw,der))
        # Closing the only GUI writer requests recovery without a STOP packet.
        os.close(cw);until(er,6,0);assert first.wait(timeout=3)==0,first.stderr.read()
        restored(first,0)
        os.close(er);running.remove((first,cw,er))
        report={'passed':True,'unnamed_pipe_eof_restores':True,'independent_process_group':True,
            'duplicate_owner_refused':True,'actual_production_owner_loop':True,
            'radio_and_manager_effects_modeled':True,'device_accessed':False,'restore_record_matches_cookie_and_eof':True,'startup_failure_record_checked':True,
            'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}}
        (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    finally:
        for p,cw,er in running:
            if p.poll() is None:os.kill(p.pid,signal.SIGKILL);p.wait(timeout=3)
            for fd in (cw,er):
                try:os.close(fd)
                except OSError:pass
        for fd in reserved:os.close(fd)
        for fd in restores.values():os.close(fd)
if __name__=='__main__':main()
