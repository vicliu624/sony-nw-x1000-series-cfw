"""Freeze reviewed startup candidate and untouched Sony updater; no deployment."""
import argparse,io,json,shutil,tarfile,time
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from prepare_managed_firmware_review import cold_start_review
from upg import STOCK_SHA256,unpack
from prepare_startup_fix_review import same_loaded_program
from review_managed_root_capacity import inventory
from remote_choice_resource import BOUND_TARGET,CONFIRM_TARGET,PAIR_TARGET

def review_wireless_delta(rp,review,upg,layout):
 shared=bool(layout.get('shared_wifi_review',layout['host_build'].get('shared_wifi_review')))
 if shared:
  baseline=private('work/startup-candidate-materials/1793858639057351161/01_PC_UPDATE/NW_WM_FW.UPG')
  assert digest(baseline)=='2328d7375e1c1a87b4ff8e1cd77a8bf6d06be0e6498fff953692a7651abb410e'
 else:
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
 added_resources=set()
 if shared:
  radio='lib/modules/sd8686.bin';supervisor='usr/local/libexec/x1000-remote-supervisor'
  binding=layout.get('remote_factory_profile',layout['host_build']['remote_factory_profile'])
  _,profile=receipt(binding['review'])
  if profile.get('device_pairing'):
   added_resources={BOUND_TARGET,CONFIRM_TARGET}
   if PAIR_TARGET in layout['files']:added_resources.add(PAIR_TARGET)
   if profile.get('embedded_runtime'):
    added_resources.update({'usr/local/libexec/x1000-remote-owner.arm','usr/local/libexec/x1000-remote-service.arm'})
  changed_resources=added_resources|({resource} if added_resources else set())
  assert {player,library,radio,supervisor}|changed_resources<=changes<={wrapper,player,library,radio,supervisor}|changed_resources,sorted(changes)
 else:
  assert {player,library,resource}<=changes<={wrapper,player,library,resource}
 def wrapper_bytes(root):
  with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:
   return archive.extractfile('./'+wrapper).read()
 loaded=same_loaded_program(wrapper_bytes(old[3]),wrapper_bytes(new[3]))
 for name in changes:
  row=layout['files'][name]
  assert after[name]['sha256']==row['sha256'] and after[name]['bytes']==row['bytes']
  if name not in before and (name==resource or name in added_resources):
   assert name not in before and (after[name]['mode'],after[name]['uid'],after[name]['gid'])==(int(row['mode'],8),row.get('uid',0),row.get('gid',0))
  else:
   assert all(before[name][key]==after[name][key] for key in ('kind','mode','uid','gid'))
 return dict(passed=True,kind='shared-wifi-delta' if shared else 'wireless-menu-delta',candidate_sha256=digest(upg),baseline_sha256=digest(baseline),
             changed_paths=sorted(changes),wrapper=loaded,original_installer_kernel_initrd_unchanged=True,
             independent_rockbox_components_equal=True,physical_wireless_menu_verified=False)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--firmware-review',required=True)
 parser.add_argument('--wifi-off-replay',help='Exact shared-Wi-Fi DSO deferred-close replay report')
 parser.add_argument('--core2-review',help='Matching Core2 app build receipt for an on-device pairing candidate')
 args=parser.parse_args()
 rp,review=receipt(args.firmware_review);upg=private(review['artifact'])
 assert digest(upg)==review['sha256'] and not review['ready_to_flash']
 inputs=review['inputs']
 for name,sha in inputs.items():assert digest(private(name))==sha
 layout_path=next(name for name in inputs if '/player-system-layout/' in name)
 _,layout=receipt(layout_path)
 shared=bool(layout.get('shared_wifi_review',layout['host_build'].get('shared_wifi_review')))
 off_review=None
 if args.wifi_off_replay:
  off_review=private(args.wifi_off_replay)
  replay=json.loads(off_review.read_text())
  cases={row['case']:row for row in replay['cases']}
  assert shared and replay['passed'] and replay['library_sha256']==layout['host_build']['library_sha256']
  assert replay['source_sha256']==digest(ROOT/'tools/test_shared_wifi_auto_off.py')
  assert cases['ready']['dispatched']==[[0x683400,0x4a0119,0xff0000,0]] and cases['busy']['pending_retained']
  assert not any(cases[name]['dispatched'] for name in ('busy','denied','left-page','changed-row','exiting','bad-image','bad-dispatch'))
 owner_update=None;pairing_service=None;core2=None;embedded=False
 if shared:
  profile=layout.get('remote_factory_profile',layout['host_build']['remote_factory_profile'])
  _,supervisor=receipt(profile['review'])
  _,owner=receipt(supervisor['shared_wifi_owner_review'])
  source=private(owner['artifact']);target=profile['inputs']['owner']
  assert owner['shared_wifi_supported'] and digest(source)==target['sha256']==owner['sha256']
  assert source.stat().st_size==target['bytes']
  embedded=bool(supervisor.get('embedded_runtime'))
  if embedded:
   assert supervisor['embedded_runtime'] and owner['root_cold_supported']
   assert target['path']=='/usr/local/libexec/x1000-remote-owner.arm'
  else:
   assert target['path']=='/contents/HOMEBREW/data/wireless-remote/runtime/owner.arm'
   owner_update=(source,target['path'].removeprefix('/contents/'),target['sha256'])
  if supervisor.get('device_pairing'):
   service=supervisor['local_inputs']['service']
   pairing_service=private(service['local'])
   assert pairing_service.stat().st_size==service['bytes'] and digest(pairing_service)==service['sha256']
   service_path=('/usr/local/libexec/x1000-remote-service.arm' if embedded else
                 '/contents/HOMEBREW/data/wireless-remote/runtime/service.arm')
   assert supervisor['inputs']['service']['path']==service_path
   if not args.core2_review:raise ValueError('On-device pairing requires the matching Core2 review')
   _,controller=receipt(args.core2_review)
   assert controller['built'] and controller['target']=='Core2 + Faces Gamepad3'
   assert controller['version']==(ROOT/'runtime/apps/wireless-remote/core2/VERSION').read_text(encoding='utf-8').strip()
   for name,sha in controller['source_hashes'].items():
    assert digest(ROOT/name)==sha,'Core2 source changed: '+name
   row=controller['artifacts']['firmware.bin'];core2=private(row['local'])
   assert core2.stat().st_size==row['bytes'] and digest(core2)==row['sha256']
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
 if comparison['kind'] in ('wireless-menu-delta','shared-wifi-delta'):
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
 if owner_update:
  source,destination,expected=owner_update
  target=out/'03_PLAYER_FILES'/destination
  target.parent.mkdir(parents=True)
  shutil.copy2(source,target)
  assert digest(target)==expected
  choice_count=layout['host_build']['wireless_composition']['initializer'].get('visible_choices',3)
  selector_note=('Wireless Mode contains Wi-Fi and Off. Wireless Remote has its own On/Off switch.'
                 if choice_count==2 else 'The ESP-NOW selector remains in this test build. The shared remote uses Wi-Fi.')
  off_step=''
  if off_review:
   shutil.copy2(off_review,out/'wifi-off-replay.json')
   off_step=('7. With remote active again, select Off in Wireless Mode and confirm once.\n'
             '   Leave the selection page open until the remote retires and Wi-Fi turns off.\n')
  (out/'READ_FIRST.md').write_text(f'''# NW-X1060 shared Wi-Fi diagnostic

For Japanese NW-X1060 on 1.11. This is a private hardware test candidate with
offline checks. It has not been installed or tested on the player.

1. Set Wireless Remote to Off. With the player connected as WALKMAN storage,
   save a PC copy of the existing HOMEBREW/data/wireless-remote/runtime/owner.arm.
2. Copy only the owner.arm from 03_PLAYER_FILES to that same path on WALKMAN.
   The new system supervisor checks its exact SHA-256. Keep service.arm,
   config.bin, session.keys and all existing packet-number journals in place.
3. Run 01_PC_UPDATE/FWUpdater.exe manually and wait for completion. Safely
   eject the player and confirm the Sony main menu is responsive.
4. Open Wireless Mode and check the choices. Select Wi-Fi and connect to the router. Confirm IP and
   ordinary network access while Wireless Remote is still Off.
5. Play a local song and enable Wireless Remote. Check that Core2 receives
   current playback state and can pause and resume. From the PC, check that
   the player remains reachable at its verified IP during the same session.
   Use the same check with remote Off as the baseline. Leave the player in
   the original interface during the check. The existing Core2 firmware uses
   channel 8, so use a 2.4 GHz test network on channel 8 for this build.
6. Turn Wireless Remote Off. Confirm ordinary network access still works.
   Record the first failed step if the behavior differs.
{off_step}

{selector_note}
If returning to the earlier custom firmware, restore its matching owner.arm
from the PC copy. The separate original Sony updater is included as an option
when USB and the updater are still available.
''',encoding='utf-8')
 if pairing_service and not embedded:
  target=out/'03_PLAYER_FILES/HOMEBREW/data/wireless-remote/runtime/service.arm'
  shutil.copy2(pairing_service,target)
  assert digest(target)==digest(pairing_service)
 if pairing_service:
  controller_dir=out/'04_CORE2';controller_dir.mkdir()
  shutil.copy2(core2,controller_dir/'firmware.bin')
  assert digest(controller_dir/'firmware.bin')==digest(core2)
  channel_help=('Select Channel in the Core2 Pairing tab to match the router.'
                if controller['version'] in ('0.1.0-alpha.17','0.1.0-alpha.18','0.1.0-alpha.19') else
                'Use channel 8, or set Core2 to the router channel with its USB console command channel N.')
  instructions=f'''# NW-X1060 pairing and shared Wi-Fi candidate

Private offline-checked candidate for Japanese NW-X1060 on the 1.11 platform.
Physical GUI, wireless pairing, USB handoff and recovery are unverified.

1. With the remote off, copy the two files under 03_PLAYER_FILES to their
   matching WALKMAN paths. On an existing installation, keep a PC copy of the
   previous owner.arm and service.arm. Do not replace configuration, keys or
   packet-number journals. A new device only needs the two app files.
2. Run 01_PC_UPDATE/FWUpdater.exe manually. Confirm update completion, then
   safely eject and check that the Sony main menu, Homebrew and Settings open.
   02_ORIGINAL_SONY contains the original updater for use when still supported
   by the device and USB connection.
3. Use the matching Core2 {controller['version']} app image in 04_CORE2.
   Select Wi-Fi on the Walkman and connect it to a 2.4 GHz router.
   {channel_help}
4. On an unpaired Core2, open Pairing and select Start pairing. On the
   Walkman, open Settings, Wireless Remote, Start Pairing. The first confirmation
   may check existing storage. Confirm again to start discovery. Once the Core2
   is found, confirming opens its address page. Go back and confirm again to
   open the keyboard. Enter the one-time code displayed on the Core2.
5. Verify the Walkman address on the Core2 and select Confirm. After the
   devices authenticate, confirm the pairing row on the Walkman again to save.
   Check that the Core2 reports Pairing saved, and that revisiting Pairing on
   the Walkman shows the correct bound MAC address.
6. Play a local track. Turn Wireless Remote on and check that Core2 shows
   track information and can pause/resume while normal Wi-Fi still works.
   Turn Remote off and confirm normal Wi-Fi remains connected. Separately test
   selecting Off in Wireless Mode while Remote is active.
7. Reopen the bound address page and go back. Select Delete and first answer
   No. Verify the binding remains. Repeat and answer Yes. Verify the remote
   can no longer control the Walkman. Remove the saved Walkman on the Core2
   before starting a new pairing.

Report the first step that differs. The current test UI uses repeated
confirmation of the pairing row to advance between pairing phases.
'''
  adapter='runtime/platform/player/remote_page_adapter.c'
  if (layout['host_build']['source_hashes'].get(adapter)==digest(ROOT/adapter) and
      'pairing_wait_tick' in (ROOT/adapter).read_text()):
   instructions=instructions.replace(
    'Walkman, open Settings, Wireless Remote, Start Pairing. The first confirmation\n'
    '   may check existing storage. Confirm again to start discovery. Once the Core2\n'
    '   is found, confirming opens its address page. Go back and confirm again to\n'
    '   open the keyboard. Enter the one-time code displayed on the Core2.',
    'Walkman, open Settings, Wireless Remote, Start Pairing and confirm once.\n'
    '   A native waiting dialog covers binding lookup and discovery. The discovered\n'
    '   Core2 address page opens automatically. Back out of that address page,\n'
    '   select Start Pairing and confirm to open the keyboard. Enter the one-time\n'
    '   code displayed on Core2. Discovery times out after 15 seconds.')
   instructions=instructions.replace(
    'devices authenticate, confirm the pairing row on the Walkman again to save.',
    'devices authenticate, the Walkman saves the verified binding automatically.')
   instructions=instructions.replace(
    'Report the first step that differs. The current test UI uses repeated\n'
    'confirmation of the pairing row to advance between pairing phases.',
    'Report the first step that differs. Pairing discovery, remote approval and\n'
    'verified storage completion have native waiting/progress handling.')
  if embedded:
   start=instructions.index('1. With the remote off')
   end=instructions.index('2. Run',start)
   instructions=instructions[:start]+('1. The firmware includes the pairing and remote programs. '
    'No remote runtime files need to be copied to WALKMAN.\n')+instructions[end:]
   instructions=instructions.replace('Select Wi-Fi on the Walkman and connect it to a 2.4 GHz router.\n   '+channel_help,
    'Select Wi-Fi on the Walkman without joining a network. Set Core2 to the\n'
    '   Walkman listener channel. The cold start uses channel 8. An already\n'
    '   powered Walkman uses its current Wi-Fi channel, which was channel 1\n'
    '   in the unassociated hardware trial.')
   instructions=instructions.replace(' while normal Wi-Fi still works','')
   instructions=instructions.replace(
    'The first confirmation\n   may check existing storage. Confirm again to start discovery.',
    'Confirm and allow time for the binding check and discovery.')
   instructions=instructions.replace('Turn Remote off and confirm normal Wi-Fi remains connected.',
    'Turn Remote off and check that Core2 loses the remote session.')
   if off_review:
    shutil.copy2(off_review,out/'wifi-off-replay.json')
   if 'runtime/platform/player/parent_trace_store.c' in layout['host_build']['source_hashes']:
    trace=out/'03_PLAYER_FILES/HOMEBREW/data/diagnostics/remote-pairing.bin'
    trace.parent.mkdir(parents=True,exist_ok=True)
    trace.write_bytes(b'X1000-REMOTE-PAIRING-TRACE-1'.ljust(2048,b'\0'))
    instructions+=('\nFor a diagnostic run, copy 03_PLAYER_FILES to WALKMAN before testing. '
                   'After one pairing attempt, retrieve remote-pairing.bin over USB.\n')
  if 'runtime/apps/wireless-remote/pairing_auto.c' in layout['host_build']['source_hashes']:
   start=instructions.index('4. On an unpaired Core2')
   end=instructions.index('6. Play a local track',start)
   instructions=instructions[:start]+('4. On an unpaired Core2, open Pairing and select Start pairing. On the\n'
    '   Walkman select Wireless Remote > Start Pairing once. Wait for the remote\n'
    '   address page, then select Yes in the native pairing confirmation.\n'
    '   No keyboard or pairing code is used. No does not create a binding.\n'
    '5. Keep both devices in pairing mode until Core2 reports Pairing saved and\n'
    '   the Walkman shows its saved remote. Key agreement and commit are automatic.\n')+instructions[end:]
   instructions=instructions.replace('Pairing discovery, remote approval and\nverified storage completion have native waiting/progress handling.',
    'Remote selection and verified storage completion have native progress handling.')
   notice=out/'THIRD_PARTY_NOTICES';notice.mkdir()
   shutil.copy2(ROOT/'third_party/bearssl-curve/LICENSE.txt',notice/'BearSSL-LICENSE.txt')
  if (layout['host_build']['source_hashes'].get(adapter)==digest(ROOT/adapter) and
      'WR_NATIVE_PAGE_BINDING_LABEL' in (ROOT/adapter).read_text()):
   start=instructions.index('7. Reopen the bound address page')
   end=instructions.index('\nReport the first step',start)
   instructions=instructions[:start]+('7. Reopen Wireless Remote. Its third row shows the saved remote MAC, not\n'
    '   Start pairing. Keep that binding for the first remote-control trial.\n'
    '   To remove it later, select the MAC row and confirm Yes; No preserves it.\n'
    '   Wait for removal to finish before starting another pairing. The Core2\n'
    '   has its own saved binding; remove that separately for a new pairing.\n')+instructions[end:]
  if embedded and 'XPN00002' in (ROOT/'runtime/platform/espnow/xnow_pn_file.c').read_text():
   instructions+=('\nCounter recovery: retain the existing pairing. Verified legacy pending counters\n'
    'are resumed without resetting them. New commits migrate to two fixed80-byte\n'
    'XPN00002 records on user storage. Do not delete either record or restore an\n'
    'older counter snapshot under the same keys. Previous firmware cannot read\n'
    'V2 counters; remote use after downgrade needs compatible state handling or\n'
    'fresh pairing. This is not a filesystem-repair or power-loss guarantee.\n')
  (out/'READ_FIRST.md').write_text(instructions,encoding='utf-8')

 manifest=dict(prepared=True,ready_to_flash=False,device_accessed=False,installed=False,
  project_version=(ROOT/'VERSION').read_text().strip(),candidate_sha256=digest(upg),
  stock_sha256=STOCK_SHA256,external_files_reinstall_required=bool(owner_update),
  owner_update_destination=owner_update[1] if owner_update else None,
  files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in out.rglob('*') if p.is_file()},
  source_hashes={'tools/prepare_startup_candidate_materials.py':digest(ROOT/'tools/prepare_startup_candidate_materials.py')})
 (out/'materials.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(dict(directory=out.relative_to(ROOT).as_posix(),candidate_sha256=digest(upg),ready_to_flash=False,device_accessed=False),indent=2))

if __name__=='__main__':main()
