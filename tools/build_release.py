"""Clean-source firmware, native apps and GitHub Release repository composition."""
from pathlib import Path
import argparse,ast,hashlib,io,json,os,re,shutil,subprocess,sys,time,zipfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
def archive(path,files):
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 with zipfile.ZipFile(path) as z:assert z.testzip() is None
def tree(folder,prefix=''):
 result={}
 for p in sorted(folder.rglob('*')):
  if p.is_symlink():raise ValueError('Linked package input: '+str(p))
  if p.is_file():result[prefix+p.relative_to(folder).as_posix()]=p.read_bytes()
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repository');parser.add_argument('--tag');parser.add_argument('--output',type=Path);parser.add_argument('--skip-bootstrap',action='store_true');a=parser.parse_args()
 os.chdir(ROOT);version=(ROOT/'VERSION').read_text().strip();policy=json.loads((ROOT/'config/release.json').read_text());repo=a.repository or policy['repository'];tag=a.tag or 'v'+version
 if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or '..' in repo:raise ValueError('Invalid repository')
 if tag!='v'+version or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',tag):raise ValueError('Tag must equal v<VERSION>')
 out=(a.output or ROOT/'dist'/version/'release').resolve()
 if not out.is_relative_to(ROOT/'dist') or out.exists():raise ValueError('Select a new dist output directory')
 out.mkdir(parents=True);upload=out/'upload';upload.mkdir();player=out/'player';apps=player/'HOMEBREW/apps';apps.mkdir(parents=True)
 work=ROOT/'work/ci'/('release-'+str(time.time_ns()));work.mkdir(parents=True);steps=[]
 def run(script,*args):
  print('BUILD',script,flush=True);log=work/(Path(script).stem+'.log');start=time.monotonic()
  with log.open('wb') as f:p=subprocess.run([sys.executable,script,*map(str,args)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
  steps.append({'script':script,'exit':p.returncode,'seconds':round(time.monotonic()-start,2)})
  if p.returncode:
   print(log.read_text(encoding='utf-8',errors='replace')[-16000:],flush=True)
   raise RuntimeError('Build failed: '+script+'; see '+str(log))
 if not a.skip_bootstrap:run('tools/ci_bootstrap.py')
 bootstrap=json.loads((ROOT/'work/ci/bootstrap.json').read_text())
 for i,sha in enumerate(bootstrap['stock_components']):assert digest((ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes())==sha
 run('tools/build_hello_app.py');run('tools/build_libc_frontend.py','--review-output','work/libc-launcher-review')
 run('tools/build_device_info.py');run('tools/build_graphics_demo.py','--review-output',str(work/'graphics'))
 run('tools/build_fm_radio.py');run('tools/build_terminal.py')
 run('tools/build_dictionary_data.py');run('tools/build_dictionary_app.py')
 run('tools/build_ebook_assets.py');run('tools/build_ebook_encoding.py');run('tools/build_ebook_app.py')
 run('tools/build_emulator_apps.py');run('tools/build_external_language_app.py')
 def copy_app(ident,source):
  dest=apps/ident;shutil.copytree(source,dest);return dest
 copy_app('hello',ROOT/'work/hello-app/package')
 copy_app('device-info',ROOT/'work/device-info-build/HOMEBREW/apps/device-info')
 copy_app('graphics-demo',work/'graphics/apps/graphics-demo')
 copy_app('fm-radio',ROOT/'work/fm-radio-review/package/HOMEBREW/apps/fm-radio')
 # Publish no private TLS identity. Personal keys live outside the replaceable app.
 terminal=apps/'terminal';terminal.mkdir();shutil.copyfile(ROOT/'work/terminal-review/terminal.arm',terminal/'app')
 copy_app('dictionary',ROOT/'work/dictionary-app/package');copy_app('ebook',ROOT/'work/ebook-app/package')
 for ident in ('gbc','tamagotchi-id'):copy_app(ident,ROOT/'work/emulator-apps'/ident/'package')
 copy_app('language',ROOT/'work/external-language-app-build/HOMEBREW/apps/language')
 lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
 flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_BUILD_VERSION="'+version+'"','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(crypto/'bearssl-0.6/inc'),'-I'+str(resolver)]
 common=['runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c','runtime/store/start.c','runtime/store/start.S']
 def compile_app(ident,sources,extra=()):
  folder=apps/ident;folder.mkdir();objects=work/(ident+'-objects');objects.mkdir();built=[]
  for i,source in enumerate(sources):
   obj=objects/(str(i)+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*[x for x in flags if not x.startswith('-Wl,')],'-c',source,'-o',str(obj)],check=True);built.append(str(obj))
  subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Wl,-rpath-link,'+str(resolver),*built,*map(str,extra),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(folder/'app')],check=True)
 for ident,file in [('diagnostics','diagnostics.c'),('key-check','key_check.c')]:compile_app(ident,['runtime/apps/'+ident+'/'+file,*common])
 # Use maintained store modules, without the historical integration-manifest gate.
 syntax=ast.parse((ROOT/'tools/build_network_store_app.py').read_text())
 modules=next(ast.literal_eval(n.value) for n in syntax.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='modules' for t in n.targets))
 compile_app('store',['runtime/store/'+n+'.c' for n in modules]+['runtime/store/start.S','runtime/native/frontend.c','runtime/native/sha256.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c'],[crypto/'arm-build/libbearssl.a',resolver/'libcares.so.2',resolver/'librt.so.1'])
 # Font source is public/pinned; generated subset carries its original notices.
 from ci_bootstrap import fetch
 font_manifest=json.loads((ROOT/'sources/qqmusic-font-source.json').read_text())
 for name,row in font_manifest['files'].items():fetch(row['url'],'work/qqmusic-font/'+name,row['sha256'])
 run('tools/subset_qqmusic_font.py')
 profile=json.loads((ROOT/'config/qqmusic-public.json').read_text());ca=(crypto/'github-ca.der').read_bytes();roots=[]
 while ca:
  count=ca[1]&127 if ca[1]&128 else 0;header=2+count;size=int.from_bytes(ca[2:header],'big') if count else ca[1];part=ca[:header+size];ca=ca[header+size:]
  root=work/f'ca-{len(roots)}.der';root.write_bytes(part);roots.append(str(root))
 profile['ca_files']=roots;profile_path=work/'qqmusic-public.json';profile_path.write_text(json.dumps(profile))
 run('tools/build_qqmusic_native.py','--profile',profile_path,'--output',work/'qqmusic','--device-full','--public-installation')
 run('tools/build_qqmusic_wifi_helper.py')
 qq=apps/'qqmusic';qq.mkdir();shutil.copyfile(work/'qqmusic/app',qq/'app');shutil.copyfile(ROOT/'work/qqmusic-wifi/wifi-helper',qq/'wifi-helper');(qq/'resources').mkdir();shutil.copyfile(ROOT/'work/qqmusic-font/QQMusicUI.otf',qq/'resources/QQMusicUI.otf')
 titles={'terminal':'WiFi Terminal','diagnostics':'Device Check','key-check':'Key Check','qqmusic':'QQ Music','store':'App Market'}
 base='https://github.com/'+repo+'/releases/download/'+tag+'/'
 catalog=[];release_apps=[]
 from release_firmware import build as firmware_build
 firmware,firmware_report=firmware_build(work/'firmware',player)
 launcher=player/'HOMEBREW/launcher';launcher.mkdir();shutil.copyfile(ROOT/'work/libc-launcher-review/launcher.elf',launcher/'app')
 for folder in sorted(apps.iterdir()):
  ident=folder.name;app=(folder/'app').read_bytes()
  notices=[]
  if ident in ('terminal','store','qqmusic'):notices.append((crypto/'bearssl-0.6/LICENSE.txt','BearSSL-MIT.txt'))
  if ident in ('dictionary','ebook'):
   for p in (ROOT/'third_party'/('dictionary-data' if ident=='dictionary' else 'ebook-data')).iterdir():
    if p.is_file():notices.append((p,p.name))
  if ident=='gbc':notices.append((ROOT/'third_party/gnuboy/COPYING','gnuboy-GPL2.txt'))
  if ident=='tamagotchi-id':notices.append((ROOT/'third_party/tama-id/core/LICENSE','Tamagotchi-GPL3.txt'))
  if ident=='qqmusic':
   for path,name in [('third_party/qqmusic-codecs/shine/COPYING','Shine-LGPL2.txt'),('third_party/qqmusic-codecs/tremor/COPYING','Tremor-BSD.txt'),('third_party/qqmusic-codecs/ogg/COPYING','Ogg-BSD.txt'),('third_party/qqmusic-stb/LICENSE','stb-LICENSE.txt'),('third_party/qmc-reference/LICENSE','QMC-MIT.txt'),('third_party/qqmusic-protocol-reference/LICENSE','Protocol-GPL3.txt'),('work/qqmusic-font/OFL.txt','Font-OFL.txt')]:notices.append((ROOT/path,name))
  if notices:
   (folder/'LICENSES').mkdir(exist_ok=True)
   for source,name in notices:shutil.copyfile(source,folder/'LICENSES'/name)
  (folder/'NOTICE.txt').write_text('Experimental Japanese X1000 native application. Dependencies retain their own notices under LICENSES. Corresponding build/source archive: '+base+'source-'+version+'.zip\nNo Sony system libraries, ROMs, account state or personal TLS keys are supplied in this application package.\n')
  elf=ELFFile(io.BytesIO(app));assert elf['e_machine']=='EM_ARM'
  old=dict(line.split('=',1) for line in (folder/'app.ini').read_text().splitlines()) if (folder/'app.ini').exists() else {}
  app_version=old.get('version',version);title=old.get('name',titles.get(ident,ident))
  metadata=f'api=1\nid={ident}\nname={title}\nversion={app_version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(app)}\nsha256={digest(app)}\n'.encode();(folder/'app.ini').write_bytes(metadata)
  data=tree(folder);data.pop('files.sha256',None)
  index=('HBFILES1\n'+''.join(f'{digest(value)} {len(value)} {name}\n' for name,value in sorted(data.items()))).encode();(folder/'files.sha256').write_bytes(index);data['files.sha256']=index
  prefix=ident+'--'
  for name,value in data.items():(upload/(prefix+name.encode('ascii').hex())).write_bytes(value)
  catalog.append('\t'.join([ident,app_version,base,str(len(metadata)),digest(metadata),str(len(index)),digest(index),prefix]))
  archive(upload/(ident+'-'+app_version+'.zip'),{'HOMEBREW/apps/'+ident+'/'+n:b for n,b in data.items()})
  release_apps.append({'id':ident,'version':app_version,'bytes':len(app),'sha256':digest(app),'files':len(data)})
 assert sorted(x['id'] for x in release_apps)==policy['apps']
 listing=('HBSTORE2\n'+'\n'.join(catalog)+'\n').encode('ascii');(upload/'catalog.tsv').write_bytes(listing)
 repository=player/'HOMEBREW/repository';repository.mkdir();trust=(crypto/'github-ca.der').read_bytes();(repository/'ca.der').write_bytes(trust)
 configuration=f'HBREPO1\ncatalog_url={base}catalog.tsv\ncatalog_bytes={len(listing)}\ncatalog_sha256={digest(listing)}\nca_sha256={digest(trust)}\n'.encode();(repository/'repository.conf').write_bytes(configuration)
 archive(upload/'market-source.zip',tree(repository,'HOMEBREW/repository/'))
 starter={**tree(launcher,'HOMEBREW/launcher/'),**tree(repository,'HOMEBREW/repository/'),**tree(apps/'store','HOMEBREW/apps/store/'),**tree(apps/'language','HOMEBREW/apps/language/'),**tree(player/'HOMEBREW/languages','HOMEBREW/languages/')}
 archive(upload/('NW-X1000-'+version+'-player-setup.zip'),starter)
 archive(upload/('NW-X1000-'+version+'-firmware.zip'),{'NW_WM_FW.UPG':firmware.read_bytes(),'README.md':(ROOT/'docs/RELEASES.md').read_bytes(),'verification.json':json.dumps(firmware_report,indent=2).encode()})
 archive(upload/'terminal-computer.zip',{'terminal_client.py':(ROOT/'tools/terminal_client.py').read_bytes(),'prepare_terminal_identity.py':(ROOT/'tools/prepare_terminal_identity.py').read_bytes(),'README.md':(ROOT/'docs/apps/TERMINAL.md').read_bytes()})
 files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
 source={n:(ROOT/n).read_bytes() for n in files if n and (ROOT/n).is_file() and not (ROOT/n).is_symlink()}
 archive(upload/('source-'+version+'.zip'),source)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 report={'version':version,'tag':tag,'repository':repo,'source_commit':commit,'apps':release_apps,'firmware':firmware_report,'catalog_sha256':digest(listing),'catalog_bytes':len(listing),'steps':steps,'source_files':len(source),'private_terminal_key_published':False,'physical_device_accessed':False,'hardware_qualified':False}
 (upload/'release-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
 (upload/'RELEASE_NOTES.md').write_text('# X1000 experimental '+version+'\n\nJapanese NW-X1050/NW-X1060 only. See the source documentation and verification reports. Firmware preserves the original installer/kernel/initrd; installation and recovery are not hardware-qualified. Copy player-setup files to visible storage before using the launcher/market. App ZIPs and catalog assets are verified independently. No account data, ROMs, music or terminal private keys are included. Terminal requires personal PC pairing.\n')
 (upload/'SHA256SUMS').write_text(''.join(digest(p.read_bytes())+'  '+p.name+'\n' for p in sorted(upload.iterdir()) if p.is_file()))
 print(json.dumps({'upload_directory':str(upload),'apps':len(release_apps),'assets':len(list(upload.iterdir())),'firmware_sha256':firmware_report['firmware_sha256']},indent=2))
if __name__=='__main__':main()
