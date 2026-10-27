"""Parse staged AppList and resolve Homebrew path in the same stock manager emulator."""
from pathlib import Path
import subprocess,sys,json,hashlib,struct
from native_lookup_fixture import lookup
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();p='work/integration-'+version+'/system-overlay/etc/AppList.conf';raw=(ROOT/p).read_bytes();rows=[]
for name,state,status in [('/contents/HOMEBREW/launcher/app',2,0),('MissingApp',2,0x111),('/contents/HOMEBREW/launcher/app',4,0x1d03)]:
 packet=struct.pack('<5I',276,0,1,36,55)+name.encode()+b'\0';packet=packet.ljust(276,b'\0')
 details={};reply,comparisons=lookup(ROOT,packet,core_state=state,config_bytes=raw,details=details);words=list(struct.unpack('<5I',reply));assert words[:4]==[20,0,36,status]
 assert details['native_parser_executed'] and details['record_count']==7
 if not status:assert words[4]==0x30001
 rows.append({'name':name,'core_state_fixture':state,'reply':words,'comparisons':comparisons,'parser':details})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'generator_source':'tools/check_homebrew_lookup_service.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':rows,'source_hashes':{p:hashlib.sha256(raw).hexdigest(),'tools/native_lookup_fixture.py':hashlib.sha256((ROOT/'tools/native_lookup_fixture.py').read_bytes()).hexdigest()},'limits':['Original1574c parses current staged configuration in the same instance before1084c/ca24/117d8/15ad0; stdio/account/allocation boundaries virtual.','strcmp/logging/IPC virtual; no process registration or device access.']}
(ROOT/'sources/native-homebrew-lookup-service.json').write_text(json.dumps(report,indent=2)+'\n');print('Original Homebrew lookup: active-state exact path resolves30001; missing/state4 reject.')
