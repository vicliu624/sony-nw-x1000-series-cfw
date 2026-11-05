"""Freeze reviewed startup candidate and untouched Sony updater; no deployment."""
import argparse,gzip,io,json,shutil,tarfile,time
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from prepare_managed_firmware_review import cold_start_review
from upg import STOCK_SHA256,unpack
from prepare_startup_fix_review import same_loaded_program
from review_managed_root_capacity import inventory

def review_wireless_delta(rp,review,upg,layout):
 baseline=private('work/managed-firmware-review/1793817320395206222/DIAGNOSTIC-REVIEW-ONLY.UPG')
 assert digest(baseline)=='0b5ede45ef0703bfdcff75a9fc1531c99f697c5e4d904a782294dd64b9516a49'
 assert review['remote_page_replay']
 old,new=(unpack(p.read_bytes(),require_stock=False)[1] for p in (baseline,upg))
 assert old[:3]==new[:3]
 for i,component in enumerate(new):
  assert component==private(rp.parent/'rockbox-check'/f'part-{i}.bin').read_bytes()
 before,after=inventory(old[3]),inventory(new[3])
 changes={name for name in before.keys()|after.keys() if before.get(name)!=after.get(name)}
 wrapper=layout['bootstrap_path'];player=layout['player_payload_path'];library='usr/local/lib/libx1000-player.so'
 resource='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-01.swd'
 assert {player,library,resource}<=changes<={wrapper,player,library,resource}
 def wrapper_bytes(root):
  with tarfile.open(fileobj=io.BytesIO(gzip.decompress(root)),mode='r:') as archive:
   return archive.extractfile('./'+wrapper).read()
 loaded=same_loaded_program(wrapper_bytes(old[3]),wrapper_bytes(new[3]))
 for name in changes:
  row=layout['files'][name]
  assert after[name]['sha256']==row['sha256'] and after[name]['bytes']==row['bytes']
  if name==resource:
   assert name not in before and (after[name]['mode'],after[name]['uid'],after[name]['gid'])==(int(row['mode'],8),row['uid'],row['gid'])
  else:
   assert all(before[name][key]==after[name][key] for key in ('kind','mode','uid','gid'))
 return dict(passed=True,kind='wireless-menu-delta',candidate_sha256=digest(upg),baseline_sha256=digest(baseline),
             changed_paths=sorted(changes),wrapper=loaded,original_installer_kernel_initrd_unchanged=True,
             independent_rockbox_components_equal=True,physical_wireless_menu_verified=False)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware-review',required=True);args=parser.parse_args()
 rp,review=receipt(args.firmware_review);upg=private(review['artifact'])
 assert digest(upg)==review['sha256'] and not review['ready_to_flash']
 inputs=review['inputs']
 for name,sha in inputs.items():assert digest(private(name))==sha
 layout_path=next(name for name in inputs if '/player-system-layout/' in name)
 _,layout=receipt(layout_path)
 delta=rp.parent/'startup-delta.json'
 if layout.get('native_remote_page_review'):
  comparison=review_wireless_delta(rp,review,upg,layout)
 else:
  _,comparison=receipt(delta)
 assert comparison['passed'] and comparison['candidate_sha256']==digest(upg)
 cold_path=review.get('cold_dso_review') or next(name for name in inputs if name.endswith('startup-exact-dso-cold.json'))
 cold_start_review(cold_path,layout)
 template=ROOT/'work/candidate6-first-device-inputs/sony-updater'
 assert digest(template/'NW_WM_FW.UPG')==STOCK_SHA256
 extracted=ROOT/'work/updater-static-review-1/extracted'
 for name in ('FWUpdater.exe','FWUpdaterCom.dll','FWUpdaterRes.dll','NW-X10X0.ini'):
  assert digest(template/name)==digest(extracted/name),name
 out=ROOT/'work/startup-candidate-materials'/str(time.time_ns());out.mkdir(parents=True)
 shutil.copytree(template,out/'01_PC_UPDATE')
 shutil.copy2(upg,out/'01_PC_UPDATE/NW_WM_FW.UPG')
 shutil.copytree(template,out/'02_ORIGINAL_SONY')
 shutil.copy2(rp,out/rp.name)
 if comparison['kind']=='wireless-menu-delta':
  (out/'wireless-menu-delta.json').write_text(json.dumps(comparison,indent=2)+'\n',encoding='utf-8')
 else:
  shutil.copy2(delta,out/delta.name)
 (out/'READ_FIRST.md').write_text('''# Private startup diagnostic candidate

This is a local review package, not a public release or a hardware-qualified fix.
Target: Japanese NW-X1050/NW-X1060; the physical unit is NW-X1060 on 1.11.
No flashing or device operation was performed while preparing these files.

## Changes

- Preserve the original AppList ID1 SpiderApp identity.
- Put the small C exec wrapper at the original player executable path.
- Relocate one player body; do not keep a second large copy.
- Delegate cold coordinator commands3/6/7 before SDK binding without poisoning
  the later managed-service exit state.
- Keep empty native exit continuation separate from new SDK admission. Repeated
  preparation remains delegated without a radio authority, or reuses the same
  verified-OFF retirement epoch when an authority is already bound.
- Recheck resource emptiness, owner/context and code/radio validity; owned,
  draining or faulted resources are not converted to empty fallback.
- Do not automatically bootstrap wireless while the managed player is exiting
  or has not yet bound its owner; normal later initialization remains possible.
- Update the Japanese Settings Pcs descriptor's two count fields, preserving
  its capacity and the original native rendering code. The superseded
  media-list constructor hooks are not part of this profile.
- Preserve Sony installer, kernel, initrd and updater behavior.

The exact failed first-fix library reproduces the command7 interception defect;
the rebuilt library delegates it. This does not prove the full physical stall
cause or a successful complete boot. QEMU cannot yet boot the stock GUI because
its DSP interface is missing. Use review.json for exact root inventory growth;
this is not a current physical free-space measurement.

## Manual first test, only when deliberately chosen

1. Keep existing external apps, pairing keys and packet-number journals.
   Do not repeat first-use provisioning, format storage or rebuild the database.
2. Connect with sufficient battery power and use 01_PC_UPDATE/FWUpdater.exe.
   Its Sony EXE, DLLs and INI are unchanged. Do not substitute another UPG.
3. Follow Sony's updater prompts. Do not reset or disconnect during updating.
4. First verify that the original main menu appears. Then check Settings:
   the Japanese top-level list should contain twelve entries, with Language
   at position11 and Wireless Remote at position12. Test English selection.
5. Enter Homebrew, open Graphics and press HOME once to return to the original
   main menu. Stop and record the screen if any step freezes. Keep remote radio
   disabled during these entry/return tests. Avoid repeated resets or
   reformatting as diagnostic substitutes.

02_ORIGINAL_SONY contains the exact original UPG and updater as a separately
retained option. It is not a guaranteed recovery method: failed installation
can leave the device unable to enumerate over USB. Flashing remains risky.

No external files are installed by this package preparation. No test keys,
packet-number seeds, account state or ROMs are bundled.
''',encoding='utf-8')
 if comparison.get('kind')=='homebrew-idle-exit-regression-delta':
  (out/'READ_FIRST.md').write_text('''# Private Homebrew entry test candidate

Japanese NW-X1050/NW-X1060 1.11 only. This is not a public release or a
hardware-qualified repair. Flashing can fail; a stock updater is not guaranteed
recovery. No device action was performed when this directory was prepared.

## Changes and limits

- Fix resource-free exit preparation so Sony-owned pending events do not
  suppress the original preparation call. SDK resources and radio retirement
  remain checked. This condition was reproduced offline, not on the player.
- Correct the third native wireless choice resource and preserve original
  resource permissions. Keep radio disabled during the entry test.
- Keep one player payload. Original updater EXE/DLL/INI, installation script,
  kernel and initrd remain unchanged. No external App update is required.
- The current UPG passes independent Rockbox extraction, reviewed root
  inventory checks and three identical container roundtrips. An earlier
  packing rejection was not captured; its cause remains unexplained.
- System-file byte accounting does not qualify physical partition free space,
  sleep/wake, USB handoff, RF or recovery. Physical Homebrew success is unproven.

## Manual test

1. Do not reinstall external files or format storage for this test.
2. If proceeding, run 01_PC_UPDATE/FWUpdater.exe manually with sufficient power.
   Keep USB connected and do not RESET during the update.
3. After the updater explicitly completes, safely eject and unplug USB.
   Confirm the stock main menu. Keep remote control disabled.
4. First select Homebrew directly, before visiting new Settings pages. If it
   freezes, stop clicking and report the screen and elapsed time.
5. Only if the app list opens, launch Graphics and press HOME once. Confirm
   return to the original main menu. Do not enable remote radio in this stage.

02_ORIGINAL_SONY retains the original package. It is not a guaranteed recovery
mode. Detailed artifact identities are in materials.json and startup-delta.json.
''',encoding='utf-8')
 if comparison['kind']=='wireless-menu-delta':
  (out/'READ_FIRST.md').write_text('''# NW-X1060 wireless menu diagnostic

Japanese NW-X1060 on 1.11 is the intended first hardware test. This candidate
has passed offline checks. Physical menu behavior, RF and system partition
free space are still unverified. The included original Sony image is a
separate option if the updater can still recognize the player.

1. Run 01_PC_UPDATE/FWUpdater.exe manually. Keep USB connected until the updater
   reports completion. After safe removal, confirm the original main menu.
2. With the remote disabled, open Homebrew, launch Graphics and press HOME.
   Confirm that one press returns to the original main menu.
3. Open Settings > Wireless Remote. Check that On and Off appear. Back out
   without changing the setting and verify that Settings and HOME respond.
4. Immediately open Wireless Mode. Verify Wi-Fi, Off and ESP-NOW, then press
   Back once. Verify that it returns to the wireless settings parent. Reopen
   Wireless Mode and select
   ESP-NOW. If the old wireless session is still closing, the selection
   should remain on ESP-NOW. Confirm it again after the session has closed.
   If Sony returns to the wireless settings parent after completion, reopen
   Wireless Mode and verify that ESP-NOW is selected.
5. Only after these checks pass, enable the remote and check the existing Core2
   pairing. Keep the existing app files, pairing and packet-number journals.
   Record the first failing step and screen if any behavior differs.

See materials.json for updater and UPG identities and wireless-menu-delta.json
for the comparison with the earlier hardware-tested Homebrew candidate.
''',encoding='utf-8')
 assert digest(out/'01_PC_UPDATE/NW_WM_FW.UPG')==review['sha256']
 assert digest(out/'02_ORIGINAL_SONY/NW_WM_FW.UPG')==STOCK_SHA256
 manifest=dict(prepared=True,ready_to_flash=False,device_accessed=False,installed=False,
  project_version=(ROOT/'VERSION').read_text().strip(),candidate_sha256=digest(upg),
  stock_sha256=STOCK_SHA256,external_files_reinstall_required=False,
  files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in out.rglob('*') if p.is_file()},
  source_hashes={'tools/prepare_startup_candidate_materials.py':digest(ROOT/'tools/prepare_startup_candidate_materials.py')})
 (out/'materials.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(directory=out.relative_to(ROOT).as_posix(),candidate_sha256=digest(upg),ready_to_flash=False,device_accessed=False),indent=2))

if __name__=='__main__':main()
