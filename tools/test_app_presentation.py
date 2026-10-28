"""Exercise external unknown-ID presentation using the actual ARM launcher."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parent))
from app_presentation import presentation
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--launcher',type=Path,default=ROOT/'work/libc-launcher-review/launcher.elf');args=parser.parse_args();launcher=args.launcher.resolve()
    lib=ROOT/'work/arm-signal-tests/lib';exe=(ROOT/'work/hello-app/package/app').read_bytes()
    with TemporaryDirectory(prefix='external-art-') as temporary:
        apps=Path(temporary);folder=apps/'never-registered';folder.mkdir();(folder/'app').write_bytes(exe)
        (folder/'app.ini').write_text(f'api=1\nid=never-registered\nname=External Example\nversion=1.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(exe)}\nsha256={hashlib.sha256(exe).hexdigest()}\n')
        def render():
            run=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),'--render',str(apps)],capture_output=True,timeout=10,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'))
            assert run.returncode==0,run.stderr
            assert len(run.stdout)==240*432*2
            return run.stdout
        fallback=render();art=folder/'presentation.bin';art.write_bytes(presentation('hello'));custom=render();assert custom!=fallback
        for malformed in (b'',b'HBART001',art.read_bytes()+b'x',b'X'*2746):
            art.write_bytes(malformed);assert render()==fallback
        art.unlink();art.symlink_to(ROOT/'runtime/apps/hello/assets/icon.png');assert render()==fallback;art.unlink()
        os.mkfifo(art);assert render()==fallback;art.unlink()
    print(json.dumps({'passed':True,'unknown_id_external_art':True,'invalid_and_link_and_fifo_fallback':True,'hardware_accessed':False}))
if __name__=='__main__':main()

