"""Original cnmgr daemon lifecycle replay, without radio or network operations."""
import json
from pathlib import Path
import struct
from stock_wifi_daemon_fixture import StockWifiDaemon

ROOT=Path(__file__).resolve().parents[1]
daemon=StockWifiDaemon(ROOT,8)
steps=[]


def record(label,replies):
    row={'step':label,'internal_state':daemon.state,'clients':daemon.reference_count,
         'replies':[(channel,struct.unpack_from('<ii',message)) for channel,message in replies],
         'driver_calls':list(daemon.driver_calls)}
    steps.append(row)
    return replies


def command(kind,channel='sub'):
    return record('command'+str(kind),daemon.command(channel,struct.pack('<I',kind)+bytes(1016)))


assert command(29) and daemon.reference_count==1
assert not command(8) and daemon.state==9
assert not record('ip-stop',daemon.ip(2)) and daemon.state==10
assert record('wlan-disconnected',daemon.wlan('DISCONNECTED')) and daemon.state==2
assert command(18)[0][1][4:8]==struct.pack('<I',3) # public ready, not internal state2
assert command(16) and daemon.state==3
assert not command(12,'main') and daemon.state==4
assert not record('set-first',daemon.wlan('SUCCESS set'))
assert not record('set-second',daemon.wlan('SUCCESS set')) and daemon.state==6
assert not record('wlan-connected',daemon.wlan('CONNECTED')) and daemon.state==7
assert record('ip-ready',daemon.ip(0)) and daemon.state==8
assert daemon.reference_count==1
assert command(18)[0][1][4:8]==struct.pack('<I',4)
assert command(30) and daemon.reference_count==0 and daemon.state==8
out=ROOT/'work/espnow-manager-lifecycle';out.mkdir(parents=True,exist_ok=True)
report={'passed':True,'daemon_sha256':daemon.sha256,'steps':steps,
        'original_daemon_instructions':True,'events_and_driver_effects_modeled':True,
        'manager_client_retained_through_reconnect':True,'device_accessed':False,
        'live_reload_or_late_idle_policy_qualified':False}
(out/'report.json').write_text(json.dumps(report,indent=2))
print('Original manager lifecycle: disconnect/IP/WLAN completion, public3/4, reconnect and retained client passed')
