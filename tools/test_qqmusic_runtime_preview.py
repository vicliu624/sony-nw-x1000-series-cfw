"""Actual preview UI/runtime dispatch with an explicitly modeled preview adapter."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-runtime-preview';w.mkdir(exist_ok=True)
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export','ui','image','runtime')
core=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in modules]+['runtime/store/https_url.c','runtime/native/sha256.c','tools/fixtures/qqmusic_runtime_preview.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-function','-isystem','third_party/qqmusic-stb']
lib=ROOT/'work/arm-signal-tests/lib';font=ROOT/'work/qqmusic-font/QQMusicUI.otf';host=w/'preview.sanitized';arm=w/'preview.arm'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address,undefined',*core,'-lm','-o',str(host)],cwd=ROOT,check=True);subprocess.run([str(host),str(font),str(w/'host.rgb565')],check=True,timeout=20)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',str(ROOT/'work/qqmusic-codec/libm.so.6'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(ROOT/'work/qqmusic-codec'),str(arm),str(font),str(w/'arm.rgb565')],check=True,timeout=20)
report={'passed':True,'host_asan_ubsan':True,'stock_arm_libc':True,'physical_device_accessed':False,'checks':['preview start clears borrowed authorization after adapter copy','import/quality/back navigation blocked while preview owns audio','back requests stop without claiming completion','restore remains active until DONE','authorization request cancellation clears queued work','expired authorization refuses start','REVIEW remains active and blocks restart','clock regression requests stop while continuing cleanup','shutdown closes preview before account logout'],'limits':['Preview/network adapters modeled; actual UI/runtime executes. No player output qualification.'],'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core}}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
