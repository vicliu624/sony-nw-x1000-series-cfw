"""Observe original client registration events with alternative manager tables.

The existing client's stock-success assertions intentionally stop a failed-name
case. Capture its machine state there; an assertion is never a boot success.
"""
import contextlib, hashlib, io, json, runpy, sys, time
from pathlib import Path
import native_lookup_fixture

ROOT=Path(__file__).resolve().parents[1]
script=ROOT/'tools/check_home_client_registration.py'
stock=ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf'
data=stock.read_bytes()
assert data.count(b'0x00000001 * SpiderApp')==1
renamed=data.replace(b'0x00000001 * SpiderApp',b'0x00000001 * /usr/local/libexec/x1000-player-start')
original=native_lookup_fixture.lookup
rows=[]
for name,config in [('preserved',data),('renamed',renamed)]:
 def lookup(*args,**kwargs):
  kwargs['config_bytes']=config
  return original(*args,**kwargs)
 native_lookup_fixture.lookup=lookup
 previous=sys.argv
 sys.argv=[str(script),'--reply-report','sources/native-home-ipc-client-registration.json','--native-event-lookup']
 failure=None;scope=None
 try:
  with contextlib.redirect_stdout(io.StringIO()):scope=runpy.run_path(str(script))
 except AssertionError as error:
  failure='stock-success assertion stopped replay'
  trace=error.__traceback__
  while trace:
   if trace.tb_frame.f_globals.get('__file__')==str(script):scope=trace.tb_frame.f_globals
   trace=trace.tb_next
 finally:
  sys.argv=previous;native_lookup_fixture.lookup=original
 assert scope is not None and scope['event_finished'], 'Unexpected failure before receiver returned'
 requests=scope['lookup_requests']
 assert [r['name'] for r in requests]==['netfront','SpiderApp']
 rows.append(dict(configuration=name,config_sha256=hashlib.sha256(config).hexdigest(),
  assertion_stop=failure,returned_to_receive=scope['event_finished'],
  queued_root_events=scope['m']['queued'],queries=[dict(name=r['name'],reply_hex=r['reply_hex']) for r in requests]))
assert rows[0]['assertion_stop'] is None and rows[1]['assertion_stop'] is not None
assert rows[0]['queued_root_events']==rows[1]['queued_root_events']==[[0x420011,0,1,0],[0x420023,0,0,0]]
assert bytes.fromhex(rows[0]['queries'][1]['reply_hex'])[12:16]==bytes(4)
assert bytes.fromhex(rows[1]['queries'][1]['reply_hex'])[12:16]==(0x111).to_bytes(4,'little')
report=dict(bounded_comparison_passed=True,observations=rows,device_accessed=False,
 finding='Failed self-name lookup does not suppress these two registration Root events; identity repair alone is not a demonstrated startup fix.',
 limits=['Original client and manager instructions execute with modeled libc, transport and registration frames.',
 'Receiver scheduling is supplied; database creation and full boot are not executed.'],
 source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),script,stock)})
out=ROOT/'work/player-registration-identity'/str(time.time_ns());out.mkdir(parents=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
