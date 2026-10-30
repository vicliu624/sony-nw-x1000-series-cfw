"""Native owner + original Sony libraries/FIFOs + original daemon instructions.

PC-only: radio actions are explicit no-op placeholders, AP/events/driver effects
are modeled. Never opens a serial port, player, system FIFO or network socket.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import tempfile
import time
from stock_wifi_daemon_fixture import StockWifiDaemon
from unicorn.arm_const import UC_ARM_REG_R0

class CurrentConfigFixture(StockWifiDaemon):
    def hook(self,uc,pc,size,unused):
        if pc==0x1150c:
            # Seed only the same synthetic AP/DHCP values as the outer fixture;
            # the real getter, locks and copy boundaries still execute below.
            source=uc.reg_read(UC_ARM_REG_R0)+64
            uc.mem_write(source,b'A\0');self.put(source+0x2a0,1)
        return super().hook(uc,pc,size,unused)

parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group()
mode.add_argument('--current-config',action='store_true');mode.add_argument('--current-rehearsal',action='store_true');mode.add_argument('--stock-reload-rehearsal',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work'/('espnow-stock-reload-transport' if args.stock_reload_rehearsal else 'espnow-current-rehearsal-transport' if args.current_rehearsal else 'espnow-current-config-transport' if args.current_config else 'espnow-manager-stock-transport')
OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib';STOCK=ROOT/'work/qqmusic-wifi';RESOLVER=ROOT/'work/stock-resolver-probe'
for path,digest in {
    STOCK/'libcnmgr.so.1':'688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1',
    RESOLVER/'libpthread.so.0':'c932fad1e83821f438add6a1e293e3ae6c41dc1e46d252053b346c73bf467474',
    LIB/'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    LIB/'ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('unqualified library')
sources=[('tools/fixtures/xnow_current_rehearsal_transport.c' if args.current_rehearsal else 'tools/fixtures/xnow_current_config_transport.c' if args.current_config else 'tools/fixtures/xnow_manager_stock_transport.c'),'tools/fixtures/qqmusic_wifi_stock_transport.c',
         'tools/fixtures/xnow_control_platform.c','runtime/platform/espnow/xnow_control.c',
         'runtime/platform/espnow/xnow_manager.c','runtime/platform/espnow/xnow_session.c',
         'runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
if args.current_rehearsal:sources+=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
app=OUT/'owner.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-Os','-Wall','-Wextra','-Werror',
                '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft',
                '-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie',
                '-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
                *sources,str(STOCK/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0'),
                str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
daemon=CurrentConfigFixture(ROOT,8);requests=[];events=[];output=bytearray();status=None;pending=None;snapshot=None
with tempfile.TemporaryDirectory(prefix='xnow-manager-stock-') as temp:
    folder=Path(temp);selector=selectors.DefaultSelector();fds={};buffers={'main':bytearray(),'sub':bytearray()}
    for channel in ('main','sub'):
        for suffix in ('req','res'):
            name=f'cnmgr_{channel}_{suffix}';os.mkfifo(folder/name)
            fds[name]=os.open(folder/name,os.O_RDWR|os.O_NONBLOCK)
        selector.register(fds[f'cnmgr_{channel}_req'],selectors.EVENT_READ,channel)
    os.mkfifo(folder/'cnmgr_event_res')
    read_out,write_out=os.pipe();os.set_blocking(read_out,False);selector.register(read_out,selectors.EVENT_READ,'output')
    errors=os.open(OUT/'qemu.log',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    cmd=[shutil.which('qemu-arm'),'-cpu','arm926',str(LIB/'ld-linux.so.3'),
         '--library-path',f'{LIB}:{RESOLVER}:{STOCK}',str(app)]
    pid=os.posix_spawn(cmd[0],cmd,{'LANG':'C','QQ_TEST_FIFO_ROOT':temp,**({'XNOW_TEST_STOCK_RELOAD':'1'} if args.stock_reload_rehearsal else {})},
                       file_actions=[(os.POSIX_SPAWN_DUP2,write_out,1),(os.POSIX_SPAWN_DUP2,errors,2)],setpgroup=0)
    os.close(write_out);os.close(errors);started=time.monotonic()
    def deliver(replies):
        for channel,message in replies:assert os.write(fds[f'cnmgr_{channel}_res'],message)==1012
    try:
        while time.monotonic()-started<12:
            now=time.monotonic()
            if pending and now>=pending[1]:
                kind=pending[0];pending=None
                assert daemon.reference_count==1
                if kind=='disconnect':
                    assert not daemon.ip(2) and daemon.state==10
                    deliver(daemon.wlan('DISCONNECTED'));assert daemon.state==2
                elif kind=='connect':
                    assert not daemon.wlan('CONNECTED') and daemon.state==7
                    pending=('ip',now+.12)
                else:deliver(daemon.ip(0));assert daemon.state==8
                events.append([kind,daemon.state,daemon.reference_count])
            for key,_ in selector.select(.01):
                data=os.read(key.fd,4096);channel=key.data
                if channel=='output':
                    output.extend(data)
                    if not data:selector.unregister(key.fd)
                    continue
                buffers[channel].extend(data)
                while len(buffers[channel])>=1020:
                    packet=bytes(buffers[channel][:1020]);del buffers[channel][:1020]
                    kind=struct.unpack_from('<I',packet)[0]
                    assert kind in (29,18,8,16,12,30,24,7),kind
                    if kind==7:
                        assert snapshot is not None and packet[8:1012]==snapshot
                    if kind==30:assert not pending and daemon.state==8 and daemon.reference_count==1
                    replies=daemon.command(channel,packet);requests.append([channel,kind,daemon.state,daemon.reference_count])
                    if kind==24:
                        assert len(replies)==1 and len(replies[0][1])==1012
                        snapshot=replies[0][1][8:];assert len(snapshot)==1004
                    if kind==8:
                        assert not replies and daemon.state==9;pending=('disconnect',time.monotonic()+.12)
                    elif kind in (12,7):
                        assert not replies and daemon.state==4
                        assert not daemon.wlan('SUCCESS set');assert not daemon.wlan('SUCCESS set')
                        assert daemon.state==6;pending=('connect',time.monotonic()+.12)
                    deliver(replies)
            reaped,code=os.waitpid(pid,os.WNOHANG)
            if reaped==pid:status=code;break
        assert status is not None,'owner process did not complete'
        output.extend(os.read(read_out,8192))
        assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==0,output.decode(errors='replace')
        assert b'XNOW_MANAGER_STOCK_TRANSPORT_PASS' in output
        assert daemon.state==8 and daemon.reference_count==0 and not pending
        assert requests[-1][1]==30
        assert any(row[1]==24 for row in requests) and any(row[1]==7 for row in requests)
        assert all(row[1]!=12 for row in requests)
        report={'passed':True,'requests':requests,'events':events,'stdout':output.decode(),
                'native_owner_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),
                'original_daemon_sha256':daemon.sha256,'original_library_and_fifo_io':True,
                'original_daemon_instructions':True,'radio_actions_placeholders':True,
                'native_controller_dispatch_executed':not (args.current_config or args.current_rehearsal),
                'production_current_rehearsal_logic':args.current_rehearsal,
                'stock_only_controller_rehearsal':args.stock_reload_rehearsal,
                'rehearsal_delay_timing_substituted':args.current_rehearsal,
                'original_current_config_roundtrip':True,'isolated_snapshot_probe':args.current_config,
                'configuration_payload_bytes_preserved':1004,
                'configuration_payload_logged':False,
                'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,"tools/stock_wifi_daemon_fixture.py",*(["runtime/platform/espnow/stock_wifi_session.c"] if args.current_rehearsal else [])]},
                'ap_events_and_driver_effects_modeled':True,'device_accessed':False,
                'physical_reload_or_restoration_qualified':False}
        (OUT/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:
        if status is None:
            if os.getpgid(pid)==pid:os.killpg(pid,signal.SIGKILL)
            os.waitpid(pid,0)
        selector.close();os.close(read_out)
        for fd in fds.values():os.close(fd)
