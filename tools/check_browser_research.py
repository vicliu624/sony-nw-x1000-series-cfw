"""Run bounded offline browser research checks; no player or network access."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
CHECKS=[
 ('check_browser_download_policy.py','native-browser-download-policy.json',3),
 ('check_browser_return_target.py','native-browser-return-target.json',6),
 ('check_browser_notification_producer.py','native-browser-notification-producer.json',3),
 ('check_browser_alarm_dispatch.py','native-browser-alarm-dispatch.json',8),
 ('check_browser_scheduled_notification.py','native-browser-scheduled-notification.json',3),
 ('check_browser_schedule_create.py','native-browser-schedule-create.json',5),
 ('check_browser_builtin_plugin.py','native-browser-builtin-plugin.json',2),
 ('check_browser_file_uri_gate.py','native-browser-file-uri-gate.json',4),
 ('check_browser_file_continuation.py','native-browser-file-continuation.json',5),
 ('inspect_browser_surface.py','browser-uri-surface.json',None),
 ('inspect_stock_network_references.py','stock-network-config-references.json',None),
 ('check_spider_network_power_callback.py','native-spider-network-power-callback.json',6),
 ('check_spider_network_event_source.py','native-spider-network-event-source.json',3),
 ('check_spider_network_parent_dispatch.py','native-spider-network-parent-dispatch.json',6),
 ('check_spider_network_event_dispatch.py','native-spider-network-event-dispatch.json',6),
 ('check_spider_browser_launch.py','native-spider-browser-launch.json',3),
]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
manifest=json.loads((area/'manifest.json').read_text())
protected=[ROOT/'VERSION',area/'manifest.json']+[area/x['path'] for x in manifest['files']]
before={str(p.relative_to(ROOT)):digest(p) for p in protected}
logdir=ROOT/'work/browser-research-checks';logdir.mkdir(exist_ok=True)
rows=[]
for tool,report,count in CHECKS:
 start=time.monotonic()
 process=subprocess.run([sys.executable,str(ROOT/'tools'/tool)],cwd=ROOT,capture_output=True,text=True,timeout=60)
 (logdir/(tool+'.log')).write_text(process.stdout+process.stderr)
 assert process.returncode==0,(tool,process.stderr[-1500:])
 path=ROOT/'sources'/report;result=json.loads(path.read_text())
 assert result['all_passed'] and result['physical_device_access'] is False
 if count is not None:assert len(result['cases'])==count
 rows.append({'tool':tool,'report':report,'report_sha256':digest(path),'case_count':count,'seconds':round(time.monotonic()-start,3)})
 print(tool+': PASS',flush=True)
producer=ROOT/'sources/native-browser-notification-producer.json'
alarm=json.loads((ROOT/'sources/native-browser-alarm-dispatch.json').read_text())
assert alarm['producer_report_sha256']==digest(producer)
network=json.loads((ROOT/'sources/native-spider-network-event-dispatch.json').read_text())
assert network['source_report_sha256']==digest(ROOT/'sources/native-spider-network-parent-dispatch.json')
after={str(p.relative_to(ROOT)):digest(p) for p in protected};assert before==after
report={'version':version,'all_passed':True,'physical_device_access':False,'case_count':sum(r['case_count'] or 0 for r in rows),'inventory_count':sum(r['case_count'] is None for r in rows),'checks':rows,'candidate_files_and_version_unchanged':before,'limits':['Bounded host checks and static inventories only; not a complete browser, startup timing or firmware boot.','Mocked services, supplied contexts and direct function entries retain each individual report limits.','No native-code entry installed, no browser webpage tested on hardware, no device qualification.']}
(ROOT/'sources/native-browser-research-suite.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS:',report['case_count'],'cases +',report['inventory_count'],'inventories; candidate and VERSION unchanged.')

