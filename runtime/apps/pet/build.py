"""Build BSOD native application and local review package. Never deploys/flashes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from sdk_services import compiler as sdk_compiler
sdk_run = sdk_compiler(Path(__file__).resolve().parent)
import argparse
import hashlib
import json
import shutil
import subprocess
from market_metadata import descriptions
from app_presentation import install_presentation
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sprites',type=Path,required=True)
    parser.add_argument('--font',type=Path,default=ROOT/'work/ebook-data/font.bin')
    parser.add_argument('--output',type=Path,default=ROOT/'work/pet-build')
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'work') or out==ROOT/'work':raise ValueError('Use project work output')
    out.mkdir(parents=True,exist_ok=True)
    version=(ROOT/'runtime/apps/pet/VERSION').read_text().strip()
    sprites=args.sprites.read_bytes()
    if len(sprites)!=9*8*96*104*3:raise ValueError('Invalid sprite record count')
    if hashlib.sha256(args.font.read_bytes()).hexdigest()!='05d7a20a4b3d3c8916d18b47bc5deba470fd9d29ea28d46fcab5acc9605c2924':raise ValueError('Unifont resource mismatch')
    lib=ROOT/'work/arm-signal-tests/lib'
    for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
        if hashlib.sha256((lib/name).read_bytes()).hexdigest()!=digest:raise ValueError('Original library mismatch')
    flags=['-I'+str(ROOT/'work/external-tls-probe/bearssl-0.6/inc'),'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
    startup=['runtime/store/start.c','runtime/store/start.S']
    libraries=[str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
    run=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
    def build(sources,dest,extra=()):sdk_run(['arm-linux-gnueabi-gcc',*flags,'-DHB_PET_VERSION="'+version+'"',*extra,*sources,*libraries,'-o',str(dest)],cwd=ROOT,check=True)
    for name,sources in [('model',['runtime/apps/pet/pet.c','tools/fixtures/pet_model.c']),('discovery-auth',['runtime/apps/pet/discovery_wire.c','runtime/store/stock_tls_compat.c','tools/fixtures/pet_discovery_wire.c']),('ui',['runtime/apps/pet/pet.c','runtime/apps/pet/ui.c','runtime/apps/pet/link_ui.c','runtime/apps/pet/text.c','tools/fixtures/pet_ui.c'])]:
        target=out/(name+'.arm');build(sources+startup,target);sdk_run(run+[str(target)],check=True,timeout=15)
    sources=[f'runtime/apps/pet/{n}.c' for n in ['app','pet','ui','storage','text','link_ui','link_client','link_pair','link_wire','discovery','discovery_wire']]+[f'runtime/native/{n}.c' for n in ['frontend','linux_devices','linux_device_io_posix','linux_signals_posix']]+['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c']+startup
    folder=out/'HOMEBREW/apps/pet';folder.mkdir(parents=True,exist_ok=True)
    app=folder/'app';build(sources,app)
    for arg in ['--help','--version']:sdk_run(run+[str(app),arg],check=True,timeout=15)
    shutil.copyfile(args.sprites,folder/'sprites.bin')
    shutil.copyfile(args.font,folder/'font.bin')
    licenses=folder/'LICENSES';licenses.mkdir(exist_ok=True)
    for name in ['UNIFONT-LICENSE.txt','UNIFONT-OFL-1.1.txt','PROVENANCE.md']:shutil.copyfile(ROOT/'third_party/ebook-data'/name,licenses/name)
    for suffix in ['svg','png']:shutil.copyfile(ROOT/'runtime/apps/pet/assets'/('icon.'+suffix),folder/('icon.'+suffix))
    install_presentation('pet',folder,version)
    shutil.copyfile(ROOT/'work/external-tls-probe/bearssl-0.6/LICENSE.txt',licenses/'BearSSL-MIT.txt')
    (folder/'about.json').write_text(json.dumps({'id':'pet','version':version,**descriptions()['pet']},indent=2)+'\n')
    loop=out/'loop.arm'
    build(['runtime/apps/pet/app.c','runtime/apps/pet/link_pair.c','runtime/apps/pet/pet.c','runtime/apps/pet/ui.c','runtime/apps/pet/link_ui.c','runtime/apps/pet/text.c','runtime/native/frontend.c','tools/fixtures/pet_app.c',*startup],loop,['-DPET_APP_TEST'])
    sdk_run(run+[str(loop),str(app)],cwd=ROOT,check=True,timeout=20)
    host_flags=[shutil.which('gcc-12') or 'gcc','-D_DEFAULT_SOURCE','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined']
    store=out/'storage.host'
    sdk_run([*host_flags,'runtime/apps/pet/pet.c','runtime/apps/pet/storage.c','tools/fixtures/pet_storage.c','-Wl,--wrap=open,--wrap=fopen,--wrap=statfs,--wrap=write,--wrap=fsync,--wrap=rename','-o',str(store)],cwd=ROOT,check=True)
    sdk_run([str(store)],check=True,timeout=20)
    render=out/'render.host'
    sdk_run([*host_flags,'runtime/apps/pet/pet.c','runtime/apps/pet/ui.c','runtime/apps/pet/link_ui.c','runtime/apps/pet/text.c','tools/fixtures/pet_render.c','-o',str(render)],cwd=ROOT,check=True)
    sdk_run([str(render),str(args.sprites.resolve()),str(out),str(args.font.resolve())],check=True,timeout=20)
    text_test=out/'text.arm';build(['runtime/apps/pet/text.c','tools/fixtures/pet_text.c',*startup],text_test)
    sdk_run(run+[str(text_test),str(args.font.resolve())],check=True,timeout=20)
    text_host=out/'text.host';sdk_run([*host_flags,'runtime/apps/pet/text.c','tools/fixtures/pet_text.c','-o',str(text_host)],cwd=ROOT,check=True)
    sdk_run([str(text_host),str(args.font.resolve())],check=True,timeout=20)
    version=(ROOT/'runtime/apps/pet/VERSION').read_text().strip()
    data=app.read_bytes();digest=hashlib.sha256(data).hexdigest()
    (folder/'app.ini').write_text(f'api=1\nid=pet\nname=BSOD Pet\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={digest}\n')
    files=sorted(p for p in folder.rglob('*') if p.is_file() and p.name!='files.sha256')
    (folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.relative_to(folder).as_posix()}\n' for p in files))
    launcher=ROOT/'work/libc-launcher-review/launcher.elf'
    check=sdk_run(run+[str(launcher),'--check',str(out/'HOMEBREW/apps')],cwd=ROOT,capture_output=True,text=True,timeout=15)
    if check.returncode or check.stdout!='pet VERIFIED\n':raise RuntimeError(check.stdout+check.stderr)
    tracked=set(sources)
    tracked.update(str(p.relative_to(ROOT)) for p in (ROOT/'runtime/apps/pet').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    tracked.update(str(p.relative_to(ROOT)) for p in (ROOT/'tools/fixtures').glob('pet*.c'))
    tracked.update(['tools/build_pet.py','tools/prepare_pet_assets.py','runtime/native/font.inc','runtime/native/frontend.h','runtime/native/linux_devices.h','runtime/native/linux_device_io.h','runtime/native/linux_signals.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h'])
    tracked.update(['third_party/ebook-data/'+n for n in ['UNIFONT-LICENSE.txt','UNIFONT-OFL-1.1.txt','PROVENANCE.md']])
    tracked.update(['runtime/apps/pet/app.json','runtime/apps/pet/assets/icon.svg','runtime/apps/pet/assets/icon.png','tools/market_metadata.py','third_party/pet-json/json.hpp','third_party/pet-json/LICENSE.MIT','tools/prepare_pet_pairing.py'])
    report={'build_passed':True,'version':version,'app_bytes':len(data),'sprite_bytes':len(sprites),'font_bytes':args.font.stat().st_size,'glyph_cache_slots':64,'render_cases':26,'checks':['ARM companion model including autonomous actions','ARM authenticated discovery MAC/nonce/pin tamper tests','paired and unpaired graphical controller including read acknowledgement and cleanup','ARM UI navigation','ARM help/version','ARM and sanitized host UTF8 Chinese/traditional/mixed text, malformed input, wrap, truncation, missing glyph and cache tests','ARM graphical loop virtual touch and failure/stop cleanup','host storage corruption and IO fault rollback with sanitizers','host renderer all nine poses and five page variants with sanitizers','native launcher package discovery'], 'hardware_tested':False,'delivery_ready':False,'pending':['rendered review','physical paired Wi-Fi/touch/HOME/USB/sleep qualification'],'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(tracked)}}
    report['build_inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [lib/'libc.so.6',lib/'ld-linux.so.3',ROOT/'work/external-tls-probe/arm-build/libbearssl.a']}
    (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
