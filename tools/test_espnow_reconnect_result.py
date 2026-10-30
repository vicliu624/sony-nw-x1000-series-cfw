"""Original daemon counterexamples: connect result4 is not a unique cause.

Offline only. Driver/AP effects are modeled; no player or network is touched.
"""
import json
from pathlib import Path
import struct
from stock_wifi_daemon_fixture import StockWifiDaemon

ROOT=Path(__file__).resolve().parents[1]


def request(daemon,kind,channel='sub'):
    return daemon.command(channel,struct.pack('<I',kind)+bytes(1016))


def setup(successes):
    daemon=StockWifiDaemon(ROOT,2)
    assert request(daemon,29) and daemon.reference_count==1
    assert request(daemon,16) and daemon.state==3
    assert not request(daemon,12,'main') and daemon.state==4
    for _ in range(successes):assert not daemon.wlan('SUCCESS set')
    return daemon


rows=[]
for successes in (0,1):
    daemon=setup(successes)
    replies=daemon.wlan('ERROR set 22')
    assert any(channel=='main' and struct.unpack_from('<i',data)[0]==4 for channel,data in replies)
    assert daemon.state==2
    public=request(daemon,18);assert struct.unpack_from('<i',public[0][1],4)[0]==3
    assert 'cnmgr_wlan_connect' not in daemon.driver_calls
    rows.append({'case':'configuration-error-'+str(successes),'wlan_event':'ERROR set 22',
                 'result':4,'final_public_state':3,'association_requested':False,
                 'cancel_requested':False,'driver_calls':daemon.driver_calls})
daemon=setup(2);assert daemon.state==6
request(daemon,27);assert daemon.state==12
replies=daemon.wlan('SUCCESS cancel')
assert any(channel=='main' and struct.unpack_from('<i',data)[0]==4 for channel,data in replies)
assert daemon.state==2
public=request(daemon,18);assert struct.unpack_from('<i',public[0][1],4)[0]==3
rows.append({'case':'explicit-cancel','result':4,'final_public_state':3,
             'association_requested':True,'cancel_requested':True,'driver_calls':daemon.driver_calls})
out=ROOT/'work/espnow-reconnect-result';out.mkdir(parents=True,exist_ok=True)
report={'passed':True,'daemon_sha256':daemon.sha256,'cases':rows,
        'result4_not_unique_to_cancellation':True,'matches_prior_result_and_public_state':True,
        'actual_failure_cause_identified':False,'original_daemon_instructions_executed':True,
        'driver_and_ap_effects_modeled':True,'device_accessed':False}
(out/'report.json').write_text(json.dumps(report,indent=2))
print('Original daemon: two configuration failures and explicit cancellation all return4/public3; live cause remains ambiguous.')
