"""Actual native fork/exec/pipe lifecycle with synthetic Wi-Fi manager only."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-wifi-tests';work.mkdir(exist_ok=True)
helper=work/'helper';flags=['-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer']
subprocess.run(['gcc-12',*flags,'runtime/apps/qqmusic/qqmusic_wifi_helper.c','tools/fixtures/qqmusic_wifi_mock.c','runtime/native/linux_signals_posix.c','-o',str(helper)],cwd=ROOT,check=True)
for name in ('ready','already','guardfail','connectfail','wait'):shutil.copyfile(helper,work/('helper-'+name));(work/('helper-'+name)).chmod(0o755)
parent=work/'parent'
subprocess.run(['gcc-12',*flags,'runtime/apps/qqmusic/qqmusic_wifi.c','tools/fixtures/qqmusic_wifi_parent.c','-o',str(parent)],cwd=ROOT,check=True)
subprocess.run([str(parent),str(work)],check=True,timeout=15)
report={'passed':True,'actual_fork_exec_and_pipe':True,'asan_ubsan':True,'stock_manager_calls_simulated':True,'checks':['start returns pending without blocking UI','cold manager power/prepare/default-connect path','existing connected interface not disconnected or reset','non-RAM IPC denied before manager init','manager failure reported','45s parent deadline initiates drain','cancel returns promptly while old connect drains','cancel ACK precedes connect completion by400ms without forced kill','no new attempt before old helper reaped','fin requires no original request inflight in shared-state fixture','controller process group is separate from caller','group TERM reaches controller without interrupting outstanding worker request','verified user-workspace lease remains held after original owner closes it','lease remains held during cancel drain and releases only after reap','cancel and exit reap only owned helper','helper receives no account/SSID/PSK via arguments or environment'],'physical_wifi_or_qq_login':False,
'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('runtime/apps/qqmusic/qqmusic_wifi_helper.c','runtime/apps/qqmusic/qqmusic_wifi.c','runtime/apps/qqmusic/qqmusic_wifi.h','tools/fixtures/qqmusic_wifi_mock.c','tools/fixtures/qqmusic_wifi_parent.c')},
'limits':['cnmgr is a synthetic shared-memory service, not the original library or daemon transport.','Physical ownership, fork use of original library handles and driver cancellation timing still require qualification.','Local native source is now bound; physical device deployment is not accepted by this test.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
