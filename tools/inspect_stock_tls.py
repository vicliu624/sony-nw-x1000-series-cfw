"""Identify stock HTTP/TLS binaries from pinned rootfs without executing them."""
from pathlib import Path
import gzip,hashlib,io,json,re,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();rootsha=hashlib.sha256(raw).hexdigest()
assert rootsha=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
rows=[];ca=None
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)),mode='r:') as tar:
 for member in tar:
  if member.name=='./etc/pki/tls/certs/ca-bundle.crt':
   ca_data=tar.extractfile(member).read();ca={'path':member.name,'bytes':len(ca_data),'sha256':hashlib.sha256(ca_data).hexdigest(),'PEM_certificate_count':ca_data.count(b'-----BEGIN CERTIFICATE-----')}
  if not member.isfile() or not any(n in member.name for n in ('libcurl.so.','libssl.so.','libcrypto.so.')):continue
  data=tar.extractfile(member).read();elf=ELFFile(io.BytesIO(data))
  strings=[m.group().decode() for m in re.finditer(rb'[ -~]{8,}',data)]
  exported=[s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF']
  dependencies=[tag.needed for tag in elf.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_NEEDED']
  rows.append({'path':member.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'version_labels':[s for s in strings if s.startswith(('libcurl/','CLIENT libcurl ','OpenSSL 0.'))],'tls_method_exports':sorted(s for s in exported if re.match(r'(?:TLS|DTLS|SSL)v.*method$',s)),'dependencies':dependencies,'certificate_path_strings':[s for s in strings if s.startswith('/') and any(n in s.lower() for n in ('cert','ca-bundle'))]})
assert len(rows)==3
report={'rootfs_sha256':rootsha,'all_passed':True,'physical_device_access':False,'libraries':rows,'stock_CA_bundle':ca,'limits':['Labels, exports and ELF dependencies only; libraries not executed or connected to a server.','No TLS1.2/1.3 method exports observed; export absence alone is not a full protocol implementation audit.','Certificate path strings do not prove the file exists, trust is current, clock is correct or verification succeeds.','No vulnerability research, bypass, network connection or changes to stock libraries.']}
(ROOT/'sources/stock-tls-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

