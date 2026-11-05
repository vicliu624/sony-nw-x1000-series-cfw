"""Static pinned manager IPC inventory; imports alone do not prove behavior."""
import hashlib,io,json,time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
pins={'sysmgrd':'131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0','appproxy':'57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'}
wanted={'sendmsg','recvmsg','socketpair','sendto','recvfrom','send','recv','fork','execve','execvp','setuid','setgid','setgroups','fcntl','close','setenv'}
rows=[]
for name,expected in pins.items():
 path=ROOT/'work/stock-manager-runtime-probe/root/usr/local/bin'/name;raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
 elf=ELFFile(io.BytesIO(raw));imports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']=='SHN_UNDEF'}
 rows.append(dict(name=name,sha256=expected,observed_imports=sorted(imports&wanted),not_observed_as_direct_imports=sorted(wanted-imports)))
out=ROOT/'work/manager-ipc-inventory'/str(time.time_ns());out.mkdir(parents=True)
report=dict(static_only=True,physical_device_access=False,binaries=rows,limits=['Missing direct imports do not exclude indirect/dynamic/shared-library implementations.','Import presence does not establish a callable descriptor-delivery protocol or authorization.','Do not inherit a boot-created service FD into every manager child as a substitute for per-session authority.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
