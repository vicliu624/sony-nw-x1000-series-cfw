"""Deferred request ownership/cancellation while platform Wi-Fi is pending."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-wifi-tests';work.mkdir(exist_ok=True)
app=work/'platform-gate'
subprocess.run(['gcc-12','-std=gnu99','-O1','-g','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined','-Wl,--gc-sections','-I'+str(ROOT/'work/stock-resolver-probe'),'-I'+str(ROOT/'work/external-tls-probe/bearssl-0.6/inc'),'tools/fixtures/qqmusic_platform_gate.c','-o',str(app)],cwd=ROOT,check=True)
subprocess.run([str(app)],check=True)
report={'passed':True,'production_program_gate':True,'asan_ubsan':True,'checks':['deferred request owns its buffer after caller erases it','no QQ send before platform ready','exact ticket/cookie owner passed once ready','cancel erases deferred request without transmission','platform failure erases deferred request','poll after cancel neither polls transport nor returns a stale response','stop arriving inside platform-ready callback prevents deferred send','stop arriving inside initial platform callback prevents immediate send'],'all_transports_simulated':True,'real_account_or_login':False}
report['source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('runtime/apps/qqmusic/qqmusic_program.c','tools/fixtures/qqmusic_platform_gate.c', 'tools/test_qqmusic_platform_gate.py')}
(work/'platform-gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
