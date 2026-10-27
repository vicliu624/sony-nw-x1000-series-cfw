"""Check saved QEMU traces case-insensitively (old socketcall uses capitals)."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
paths=['sources/native-network-external-layout.json','sources/native-network-store-candidate-failure.json','sources/native-stock-transfer-probe.json','sources/native-external-tls-probe.json','sources/native-external-tls-handshake.json','sources/native-tls-platform-probe.json','sources/native-socket-step-tests.json','sources/native-connect-step-tests.json','sources/native-connect-loopback-tests.json','sources/native-stock-resolver-probe.json','sources/native-stock-resolver-tests.json','sources/native-download-task-tests.json','sources/native-package-download-task-tests.json','sources/native-network-package-install-tests.json','sources/native-network-package-job-tests.json','sources/native-network-job-ui-tests.json','sources/native-remote-metadata-ui-tests.json','sources/native-remote-store-tests.json','sources/native-repository-remote-store-tests.json','sources/native-real-app-install-tests.json','sources/native-arm-signal-tests.json','sources/native-arm-process-tests.json','sources/native-loop-tests.json','sources/native-display-loop-tests.json','sources/native-full-loop-tests.json','sources/native-arm-cooperative-child-tests.json','sources/native-network-app-signal-tests.json','sources/native-remote-store-signal-tests.json','sources/native-payload-signal-tests.json']
rows=[]
for path in paths:
 p=ROOT/path;report=json.loads(p.read_text());assert report['all_bounded_checks_passed']
 connection_only=path=='sources/native-connect-step-tests.json'
 tcp_only=path=='sources/native-connect-loopback-tests.json'
 dns_only=path=='sources/native-stock-resolver-tests.json'
 task_only=path in ('sources/native-download-task-tests.json','sources/native-package-download-task-tests.json','sources/native-network-package-install-tests.json','sources/native-network-package-job-tests.json','sources/native-network-job-ui-tests.json','sources/native-remote-metadata-ui-tests.json','sources/native-remote-store-tests.json','sources/native-repository-remote-store-tests.json','sources/native-real-app-install-tests.json','sources/native-remote-store-signal-tests.json','sources/native-payload-signal-tests.json')
 traces=[] if connection_only or tcp_only or dns_only or task_only else ([case['trace'] for case in report['cases']] if path=='sources/native-arm-process-tests.json' else [report['trace']])
 local_traces=[report['trace']] if connection_only else []
 tcp_traces=[report['trace']] if tcp_only else []
 dns_traces=[report['trace']] if dns_only else []
 task_traces=[report['trace']] if task_only else []
 for variant in ('host_OS_entropy_clock_variant','local_socketpair_variant','https_file_controller_variant'):
  if variant in report:traces.append(report[variant]['trace'])
 for trace in traces:
  assert not any(call in trace.lower() for call in ('connect(','bind(','listen(','accept(','sendto(','sendmsg(')),path
 if 'local_connection_controller_variant' in report:local_traces.append(report['local_connection_controller_variant']['trace'])
 for trace in local_traces:
  families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower())
  assert families and all('_unix' in family or '_local' in family for family in families),path
  assert not any(call in trace.lower() for call in ('sendto(','sendmsg(')),path
 if 'loopback_tcp_controller_variant' in report:tcp_traces.append(report['loopback_tcp_controller_variant']['trace'])
 for trace in tcp_traces:
  families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower())
  operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect)\(',line,re.I)]
  assert families and all(f.strip() in ('pf_inet','af_inet') for f in families),path
  assert operations and all('127.0.0.1' in line for line in operations),path
  assert not any(call in trace.lower() for call in ('sendto(','sendmsg(')),path
 for trace in dns_traces:
  families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower())
  operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
  assert families and all(f.strip() in ('pf_inet','af_inet') for f in families),path
  assert operations and all('127.0.0.1' in line for line in operations),path
 for trace in task_traces:
  families=re.findall(r'\bsocket\(([^,\n]+)',trace.lower())
  operations=[line for line in trace.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
  assert families and all(f.strip() in ('pf_inet','af_inet') for f in families),path
  assert operations and all('127.0.0.1' in line or '127.0.0.2' in line for line in operations),path
 for checked in report.get('launcher_checks',[]):
  trace=checked['trace'].lower()
  assert not any(call in trace for call in ('socket(','connect(','bind(','sendto(','/dev/fb','/dev/icx_touch_screen')),path
 if 'execution_trace' in report:
  trace=report['execution_trace'].lower()
  assert not any(call in trace for call in ('socket(','connect(','bind(','sendto(','/dev/fb','/dev/input')),path
 if 'generator_source' in report:
  assert hashlib.sha256((ROOT/report['generator_source']).read_bytes()).hexdigest()==report['generator_sha256'],path
 for source,digest in report.get('source_hashes',{}).items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,(path,source)
 for source,digest in report.get('platform_source_hashes',{}).items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,(path,source)
 for source,digest in report.get('local_socketpair_variant',{}).get('source_hashes',{}).items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,(path,source)
 for source,digest in report.get('https_file_controller_variant',{}).get('source_hashes',{}).items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,(path,source)
 for source,digest in report.get('local_connection_controller_variant',{}).get('source_hashes',{}).items():assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest()==digest,(path,source)
 rows.append({'report':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'traces_checked':len(traces),'local_connection_traces_checked':len(local_traces),'loopback_connection_traces_checked':len(tcp_traces),'loopback_DNS_traces_checked':len(dns_traces),'owned_task_traces_checked':len(task_traces)})
out={'all_bounded_checks_passed':True,'physical_device_access':False,'case_insensitive_syscall_check':True,'evidence':rows,'limits':['Saved successful QEMU traces only, not a live network policy or sandbox.','Legacy fixtures forbid endpoint operations; connection fixtures restricted to Unix or numeric127.0.0.1 traces.','No external network/device qualification.']}
(ROOT/'sources/offline-transfer-trace-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('Offline transfer traces: case-insensitive syscall and source checks passed.')
