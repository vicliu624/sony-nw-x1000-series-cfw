"""Prepare hash-verified clean-build inputs. PC only; no historical package inputs."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,ssl,subprocess,sys,tarfile,time,urllib.request
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def fetch(url,path,digest):
 path=ROOT/path;path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and sha(path.read_bytes())==digest:return path
 for attempt in range(3):
  try:
   request=urllib.request.Request(url,headers={'User-Agent':'X1000-CI/1'})
   with urllib.request.urlopen(request,timeout=120) as response:data=response.read()
   if sha(data)!=digest:raise ValueError('Input SHA-256 mismatch: '+url)
   temporary=path.with_suffix(path.suffix+'.partial');temporary.write_bytes(data);temporary.replace(path);return path
  except Exception:
   if attempt==2:raise
   time.sleep(2)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock-exe',type=Path);p.add_argument('--skip-data',action='store_true');a=p.parse_args()
 original=json.loads((ROOT/'sources/downloads.json').read_text())[0]
 exe=a.stock_exe or fetch(original['url'],original['path'],original['sha256'])
 if sha(exe.read_bytes())!=original['sha256']:raise ValueError('Wrong Japanese updater')
 packed=subprocess.check_output(['7z','x','-so',str(exe),'/NW_WM_FW.UPG'])
 if sha(packed)!='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b':raise ValueError('Wrong UPG')
 sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
 _,parts=unpack(packed)
 upg=ROOT/'work/upg-jp';upg.mkdir(parents=True,exist_ok=True)
 for i,data in enumerate(parts):(upg/f'verified-{i}.bin').write_bytes(data)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as t:
  names=set(t.getnames())
  def get(name):
   return t.extractfile(next(x for x in ('./lib/'+name,'./usr/lib/'+name) if x in names)).read()
  lib=ROOT/'work/arm-signal-tests/lib';lib.mkdir(parents=True,exist_ok=True)
  for name in ('libc.so.6','ld-linux.so.3'):
   (lib/name).write_bytes(get(name));(lib/name).chmod(0o755)
  resolver=ROOT/'work/stock-resolver-probe';resolver.mkdir(parents=True,exist_ok=True)
  copied=set()
  def copy_library(name):
   if name in copied:return
   data=get(name);copied.add(name);(resolver/name).write_bytes(data);(resolver/name).chmod(0o755)
   elf=ELFFile(io.BytesIO(data));dynamic=elf.get_section_by_name('.dynamic')
   if dynamic:
    for tag in dynamic.iter_tags():
     if tag.entry.d_tag=='DT_NEEDED':copy_library(tag.needed)
  for name in ('libcares.so.2','libpthread.so.0','librt.so.1','libm.so.6'):copy_library(name)
  codec=ROOT/'work/qqmusic-codec';codec.mkdir(parents=True,exist_ok=True);(codec/'libm.so.6').write_bytes(get('libm.so.6'))
  target=ROOT/'work/targets-jp';target.mkdir(parents=True,exist_ok=True)
  for m in t:
   if m.isfile() and (m.name.startswith('./lib/modules/') or m.name in ['./usr/local/bin/'+n for n in ('SpiderApp','sysmgrd','appproxy','Responder')]):(target/Path(m.name).name).write_bytes(t.extractfile(m).read())
 fetch('https://raw.githubusercontent.com/c-ares/c-ares/cares-1_5_2/ares.h','work/cares-1_5_2-ares.h','ed0804876d9dc6846acd30165ccc5a866cd7e6987aa5907adb53130dc3868f04')
 shutil.copyfile(ROOT/'work/cares-1_5_2-ares.h',resolver/'ares.h')
 bear=fetch('https://www.bearssl.org/bearssl-0.6.tar.gz','work/bearssl-0.6.tar.gz','6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14')
 crypto=ROOT/'work/external-tls-probe';crypto.mkdir(parents=True,exist_ok=True)
 with tarfile.open(bear) as t:t.extractall(crypto,filter='data')
 source=crypto/'bearssl-0.6';arm=crypto/'arm-build';host=ROOT/'work/repository-config-tools/bearssl-host'
 for build,cc,ar,flags in [(arm,'arm-linux-gnueabi-gcc','arm-linux-gnueabi-ar','-Os -march=armv5te -marm -mfloat-abi=soft -ffreestanding -fno-builtin -DBR_USE_URANDOM=0'),(host,'gcc','ar','-O2')]:
  subprocess.run(['make','-C',str(source),'-j4','lib','CC='+cc,'AR='+ar,'CFLAGS='+flags,'BUILD='+str(build)],check=True,stdout=subprocess.DEVNULL)
 # Public roots are taken only from an OS-verified chain, never unverified peer data.
 roots={};context=ssl.create_default_context()
 import socket
 for hostname in ('github.com','api.github.com','release-assets.githubusercontent.com','u.y.qq.com','ssl.ptlogin2.qq.com','graph.qq.com'):
  with socket.create_connection((hostname,443),timeout=20) as raw,context.wrap_socket(raw,server_hostname=hostname) as sock:
   chain=sock._sslobj.get_verified_chain();cert=chain[-1]
   pem=cert.public_bytes() if hasattr(cert,'public_bytes') else ssl.DER_cert_to_PEM_cert(cert)
   if isinstance(pem,bytes):pem=pem.decode('ascii')
   der=ssl.PEM_cert_to_DER_cert(pem);roots[sha(der)]=der
 bundle=b''.join(roots.values());assert 0<len(bundle)<=8192 and len(roots)<=8
 (crypto/'github-ca.der').write_bytes(bundle)
 if not a.skip_data:
  fetch('https://raw.githubusercontent.com/skywind3000/ECDICT/ab22ad36302cafc6349a050e2b60894855208055/ecdict.csv','work/dictionary-inputs/ecdict.csv','d1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc')
  fetch('https://unifoundry.com/pub/unifont/unifont-16.0.04/font-builds/unifont-16.0.04.hex.gz','work/dictionary-inputs/unifont-16.0.04.hex.gz','f9c8c7802453f47be02677176aeac2342ee96d354fad7a26cedcce48e68e1d9f')
 for name in ('dictionary-data','ebook-data','ci'):(ROOT/'work'/name).mkdir(parents=True,exist_ok=True)
 report={'stock_upg_sha256':sha(packed),'stock_components':[sha(x) for x in parts],'github_root_sha256':list(roots),'github_ca_bundle_sha256':sha(bundle),'device_accessed':False,'historical_package_inputs':False}
 (ROOT/'work/ci/bootstrap.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
