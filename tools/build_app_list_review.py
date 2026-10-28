"""Build launcher/market UI review ZIP only; no firmware or device writes."""
from pathlib import Path
import ast, hashlib, json, os, shutil, subprocess, sys, zipfile
from market_metadata import write_header,descriptions
ROOT=Path(__file__).resolve().parents[1]

def main():
    os.chdir(ROOT);os.environ['QEMU_UNSET_ENV']='LD_LIBRARY_PATH,LD_PRELOAD'
    write_header()
    work=ROOT/'work/app-list-review';work.mkdir(exist_ok=True)
    subprocess.run([sys.executable,'tools/build_libc_frontend.py','--review-output','work/launcher-icons-review'],check=True)
    version=(ROOT/'VERSION').read_text().strip();lib=ROOT/'work/arm-signal-tests/lib';sdk=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe'
    recipe=json.loads((ROOT/'runtime/apps/store/build.json').read_text())
    sources=[name[2:] if name.startswith('@/') else 'runtime/apps/store/'+name for name in recipe['sources']]
    flags=['-std=gnu99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE','-DHB_USE_POSIX_DEVICE_IO','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-DHB_BUILD_VERSION="'+version+'"','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-I'+str(crypto/'bearssl-0.6/inc'),'-I'+str(sdk)]
    objects=[]
    for i,source in enumerate(sources):
        obj=work/(str(i)+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',source,'-o',str(obj)],check=True);objects.append(str(obj))
    player=work/'player';store=player/'HOMEBREW/apps/store';store.mkdir(parents=True,exist_ok=True)
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(sdk),*objects,str(crypto/'arm-build/libbearssl.a'),str(sdk/'libcares.so.2'),str(sdk/'librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(store/'app')],check=True)
    base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(sdk),str(store/'app')]
    for args,code in [(['--help'],0),(['--version'],0),([],64)]:
        run=subprocess.run(base+args,capture_output=True,text=True,timeout=15);assert run.returncode==code,(args,run.returncode,run.stdout,run.stderr)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    app=(store/'app').read_bytes();(store/'app.ini').write_text(f'api=1\nid=store\nname=App Market\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(app)}\nsha256={sha(app)}\n')
    (store/'app-info.json').write_text(json.dumps(dict(descriptions()['store'],id='store',version=version),indent=2)+'\n')
    for suffix in ('png','svg'):shutil.copyfile(ROOT/'runtime/apps/store/assets'/('icon.'+suffix),store/('icon.'+suffix))
    from app_presentation import install_presentation
    install_presentation('store',store,version)
    licenses=store/'LICENSES';licenses.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'third_party/qqmusic-stb/Noto-OFL.txt',licenses/'Noto-OFL.txt')
    shutil.copyfile(crypto/'bearssl-0.6/LICENSE.txt',licenses/'BearSSL-MIT.txt')
    inventory='HBFILES1\n'+''.join(f'{sha(p.read_bytes())} {p.stat().st_size} {p.relative_to(store).as_posix()}\n' for p in sorted(store.rglob('*')) if p.is_file() and p.name!='files.sha256')
    (store/'files.sha256').write_text(inventory)
    launcher=player/'HOMEBREW/launcher';launcher.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'work/launcher-icons-review/launcher.elf',launcher/'app')
    shutil.copyfile(ROOT/'third_party/qqmusic-stb/Noto-OFL.txt',launcher/'Noto-OFL.txt')
    instructions='''# Application list UI review

Japanese X1000 with an existing Homebrew setup only. This is a local UI review,
not a newly published firmware release. No UPG or system files are included.
Exit all Homebrew apps and connect USB. Back up the existing HOMEBREW/launcher/app
and HOMEBREW/apps/store folder on the computer, then merge this HOMEBREW folder
onto visible user storage. Safely eject USB before opening Homebrew.
Existing apps and repository settings stay in place. Roll back by restoring the
backed-up launcher and store. Physical touch/display qualification is pending.
The artwork is compiled in; installed app packages need no change to show icons.
The updated market opens app details before payload download, compares verified
installed bundles using SemVer, and requires extra approval for downgrades.
Older catalogs remain readable: known apps have a built-in introduction, while
version-specific changes require an HBSTORE3 source. Source snapshots remain
explicitly selected using their market-source.zip; this is not automatic latest
release discovery. Unknown/damaged local installs and equal-version conflicts are
blocked rather than silently overwritten. The running market is PC-updated only.
'''
    out=ROOT/'dist'/version/'app-list-review';out.mkdir(parents=True,exist_ok=True)
    archive=out/'X1000-app-list-ui-review.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.md',instructions)
        for p in sorted(player.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(player).as_posix())
    report={'launcher_bytes':(launcher/'app').stat().st_size,'market_bytes':len(app),'review_zip':str(archive.relative_to(ROOT)),'sha256':sha(archive.read_bytes()),'firmware_created':False,'device_accessed':False}
    (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
