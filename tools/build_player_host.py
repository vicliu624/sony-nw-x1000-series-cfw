"""Build an analysis-only owner-loop DSO and one-instruction ELF candidate."""
from pathlib import Path
import contextlib,hashlib,io,json,struct,subprocess,runpy,time
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
CORE_SOURCES=['runtime/platform/player/host_hook.c','runtime/platform/player/host_pid.S','runtime/platform/player/client.c','runtime/platform/player/stock_provider.c','runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_gui.c','runtime/platform/player/stock_volume.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c']
SOURCES=CORE_SOURCES+['runtime/platform/player/host_source.c','runtime/platform/player/source_service.c','runtime/platform/player/source_intent.c','runtime/platform/player/stock_source.c','runtime/platform/player/host_service.c','runtime/platform/player/host_queue.c','runtime/platform/player/rpc_wire.c','runtime/platform/player/rpc_posix.c','runtime/platform/player/stock_media.c','runtime/platform/player/stock_query.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/media_text.c','runtime/platform/player/metadata_async.c','runtime/platform/player/audio_check_async.c','runtime/platform/player/stock_queue_owner.c','runtime/platform/player/queue_capture.c','runtime/platform/player/queue_exchange.c','runtime/platform/player/queue_browser.c','runtime/platform/player/queue_page.c','runtime/platform/player/group_reader.c','runtime/platform/player/group_native.c','runtime/platform/player/queue_async.c','runtime/platform/player/player_broker.c','runtime/store/deadline.c']
STOCK_SHA='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
ENGINE_SOURCES=['runtime/platform/player/engine_provider.c','runtime/platform/player/stock_engine_control.c']
MANAGED_SOURCES=['runtime/platform/player/'+n+'.c' for n in ('host_managed_service','managed_host','managed','managed_rpc','managed_channel','managed_control','session_offer','service_drain','deferred_prepare')]+['runtime/platform/services/'+n+'.c' for n in ('session','request','events','descriptor')]
MANAGED_SOURCES+=['runtime/platform/player/host_inherited.c']
PREPARE_SOURCES=['runtime/platform/player/host_prepare_bridge.c','runtime/platform/player/stock_prepare_view.c','runtime/platform/player/stock_play_mode.c','runtime/platform/player/play_mode.c']
def patch_owner_anchor(stock):
    """Analysis primitive; caller must qualify the complete base composition."""
    elf=ELFFile(io.BytesIO(stock));segments=list(elf.iter_segments())
    if elf.elfclass!=32 or not elf.little_endian or elf['e_machine']!='EM_ARM' or elf['e_type']!='ET_EXEC':raise ValueError('Expected fixed-address ARM32 executable')
    symbols={symbol.name:symbol['st_value'] for symbol in elf.get_section_by_name('.dynsym').iter_symbols()}
    if symbols.get('getpid')!=0xda84:raise ValueError('Unexpected original getpid PLT')
    address=0xff3c;offset=next(s['p_offset']+address-s['p_vaddr'] for s in segments if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+8<=s['p_vaddr']+s['p_filesz'])
    before,next_instruction=struct.unpack_from('<II',stock,offset)
    if (before,next_instruction)!=(0xeb025a89,0xeb0008a9):raise ValueError('Unexpected owner-loop call sequence')
    after=0xeb000000|(((0xda84-address-8)//4)&0xffffff)
    if after!=0xebfff6d0:raise ValueError('Unexpected ARM call encoding')
    candidate=bytearray(stock);struct.pack_into('<I',candidate,offset,after)
    if candidate[:offset]!=stock[:offset] or candidate[offset+4:]!=stock[offset+4:]:raise ValueError('Changes escaped the anchor instruction')
    check=ELFFile(io.BytesIO(candidate))
    if check.header!=elf.header or [dict(s.header) for s in check.iter_segments()]!=[dict(s.header) for s in segments]:raise ValueError('ELF headers changed')
    return bytes(candidate),dict(address=hex(address),before=hex(before),after=hex(after),original_target='0xa6968',new_target='0xda84',return_site='0xff40')

def build(engine_provider=False,managed_host=False,native_prepare=False,builtin_localization=False,native_remote_settings=False,native_wireless_settings=False,native_rf_gate=False,remote_profile=None,native_sleep_analysis=False,review_output=None,native_remote_page_analysis=False):
    if native_remote_page_analysis and not (remote_profile and review_output):
        raise ValueError('Remote page analysis requires a remote factory profile and private review output')
    if native_sleep_analysis and not (native_rf_gate and native_prepare):raise ValueError('Sleep analysis requires paired RF/native preparation')
    if remote_profile is not None and not (native_rf_gate and native_remote_settings):raise ValueError('Remote factory requires the paired RF/Settings profile')
    if native_rf_gate and not native_wireless_settings:raise ValueError('RF gate requires the paired wireless/native-prepare profile')
    if native_wireless_settings and not (builtin_localization and native_prepare):raise ValueError('Wireless callback requires built-in/native-prepare composition')
    if native_remote_settings and not (builtin_localization and native_prepare):raise ValueError('Native Settings requires the built-in/native-prepare analysis profile')
    if builtin_localization and not native_prepare:raise ValueError('Built-in localization requires the explicit native-prepare profile')
    if native_prepare:managed_host=True
    sources=SOURCES+(ENGINE_SOURCES if engine_provider else [])
    if managed_host:sources=[p for p in sources if p not in ('runtime/platform/player/host_service.c','runtime/platform/player/rpc_posix.c')]+MANAGED_SOURCES
    if native_prepare:sources+=PREPARE_SOURCES
    if native_sleep_analysis:sources+=['runtime/platform/player/'+n+'.c' for n in ('sleep_native','sleep_host','sleep_retirement')]
    if native_remote_settings:sources+=['runtime/apps/wireless-remote/settings_backend.c','runtime/apps/wireless-remote/supervisor_process.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
    if native_wireless_settings:sources+=['runtime/platform/wireless/native_setting.c','runtime/platform/wireless/mode_policy.c']
    if native_rf_gate:
        sources+=['runtime/platform/wireless/'+n+'.c' for n in ('native_rf_dispatch','native_rf_guard','native_rf_worker','native_permission','native_offer','native_delivery','native_retirement','native_stop','native_boot','native_bootstrap','native_publisher','radio_modules','mode_client','mode_channel')]
        sources+=['runtime/platform/player/wireless_host.c','runtime/platform/player/wireless_auto.c','runtime/platform/player/host_handoff_bridge.c']
        if native_remote_settings:sources+=['runtime/apps/wireless-remote/settings_factory.c']
        if remote_profile is not None:sources+=['runtime/platform/player/remote_auto.c','runtime/platform/player/remote_ready.c']
        sources+=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
        sources=list(dict.fromkeys(sources))
    name='player-host'+('-managed' if managed_host else '')+('-engine' if engine_provider else '')+('-prepare' if native_prepare else '')
    if builtin_localization:name+='-builtin-language'
    if native_remote_settings:name+='-native-settings'
    if native_wireless_settings:name+='-wireless-settings'
    if native_rf_gate:name+='-rf-gate'
    if remote_profile is not None:name+='-remote-factory'
    if native_sleep_analysis:name+='-sleep-analysis'
    if review_output is not None:
        work=(ROOT/review_output).resolve()
        if not work.is_relative_to(ROOT/'work') or work==ROOT/'work' or work.exists():raise ValueError('Review output must be a new private directory under work')
        work.mkdir(parents=True)
    else:
        work=ROOT/'work'/name;work.mkdir(exist_ok=True)
    lib=ROOT/'work/arm-signal-tests/lib';extra=ROOT/'work/player-sqlite-ro'
    library=work/'libx1000-player-analysis.so'
    native_flags=['-DXW_PLAYER_NATIVE_REMOTE_SETTINGS'] if native_remote_settings else []
    factory_profile=None
    if remote_profile is not None:
        profile_path=Path(remote_profile).resolve()
        if not profile_path.is_relative_to(ROOT/'work'):raise ValueError('Use a private reviewed profile under work')
        profile=json.loads(profile_path.read_text(encoding='utf-8'))
        if not profile.get('built') or not profile.get('reusable_sessions'):raise ValueError('Reusable supervisor review required')
        executable=(ROOT/profile['artifact']).resolve()
        if not executable.is_relative_to(ROOT/'work'):raise ValueError('Supervisor artifact must stay under work')
        payload=executable.read_bytes()
        if len(payload)!=profile['bytes'] or not 0<len(payload)<=1048576 or hashlib.sha256(payload).hexdigest()!=profile['sha256']:raise ValueError('Supervisor identity mismatch')
        for name,digest in profile['source_hashes'].items():
            source=(ROOT/name).resolve()
            if not source.is_relative_to(ROOT) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Supervisor source identity changed: '+name)
        factory_header=work/'remote_factory_profile.h'
        factory_header.write_text('#ifndef XW_REMOTE_FACTORY_PROFILE_H\n#define XW_REMOTE_FACTORY_PROFILE_H\n#define XW_PLAYER_REMOTE_FACTORY\n#define WR_REMOTE_SUPERVISOR_BYTES '+str(len(payload))+'u\n#endif\n')
        if profile.get('owner_mode_view_forwarded'):
            factory_header.write_text(factory_header.read_text()+'#define WR_REMOTE_OWNER_VIEW\n')
        native_flags+=['-I',str(work),'-include',str(factory_header)]
        factory_profile=dict(review=profile_path.relative_to(ROOT).as_posix(),supervisor_artifact=executable.relative_to(ROOT).as_posix(),sha256=profile['sha256'],bytes=len(payload),inputs=profile['inputs'],software_admission_only=True,hardware_qualified=False)
        factory_profile['owner_mode_view_forwarded']=bool(profile.get('owner_mode_view_forwarded'))
    wireless_composition=None;rf_composition=None;sleep_composition=None
    if native_wireless_settings:
        from wireless_callback_bridge import compose
        with contextlib.redirect_stdout(io.StringIO()):wireless_base=runpy.run_path(str(ROOT/'tools/test_builtin_player_composition.py'),init_globals={'native_settings_profile':native_remote_settings})
        wireless_candidate,wireless_composition=compose(wireless_base['artifact'].read_bytes(),work/'wireless-callback')
        from wireless_init_bridge import compose as compose_init
        wireless_candidate,wireless_init=compose_init(wireless_candidate,work/'wireless-init')
        wireless_composition['initializer']=wireless_init
        wireless_composition['source_hashes'].update(wireless_init['source_hashes'])
        wireless_composition['candidate_sha256']=hashlib.sha256(wireless_candidate).hexdigest()
        header=work/'wireless-profile.h'
        def digest_initializer(value):return '{'+','.join('0x'+value[i:i+2] for i in range(0,64,2))+'}'
        header.write_text('#define XW_PLAYER_NATIVE_WIRELESS_SETTINGS\n'+
            '#define XW_WIRELESS_INIT_CALLER '+wireless_init['request_caller']+'u\n'+
            '#define XW_WIRELESS_INIT_BYTES '+str(wireless_init['code_bytes'])+'u\n'+
            '#define XW_WIRELESS_INIT_DIGEST '+digest_initializer(wireless_init['guards'][0]['sha256'])+'\n'+
            '#define XW_WIRELESS_INIT_POINTER_DIGEST '+digest_initializer(wireless_init['guards'][1]['sha256'])+'\n'+
            '#define XW_WIRELESS_ENTRY '+wireless_composition['entry']+'u\n'+
            '#define XW_WIRELESS_CALLER '+wireless_composition['request_caller']+'u\n'+
            '#define XW_WIRELESS_CODE_BYTES '+str(wireless_composition['code_bytes'])+'u\n'+
            '#define XW_WIRELESS_CODE_DIGEST '+digest_initializer(wireless_composition['code_sha256'])+'\n'+
            '#define XW_WIRELESS_POINTER_DIGEST '+digest_initializer(wireless_composition['pointer_sha256'])+'\n')
        native_flags+=['-include',str(header)]
        if native_rf_gate:
            from native_rf_bridge import compose as compose_rf
            wireless_candidate,rf_composition=compose_rf(wireless_candidate,work/'rf-anchor',native_handoff=True)
            rf_header=work/'rf-profile.h'
            guards=','.join('{'+g['address']+'u,'+str(g['bytes'])+'u,'+digest_initializer(g['sha256'])+'}' for g in rf_composition['guards']+wireless_init['guards'])
            rf_header.write_text('#define XW_PLAYER_NATIVE_RF\n#define XW_NATIVE_RF_GUARDS {'+guards+'}\n')
            native_flags+=['-include',str(rf_header)]
            if native_sleep_analysis:
                from native_sleep_bridge import compose as compose_sleep
                wireless_candidate,sleep_composition=compose_sleep(wireless_candidate,work/'sleep-anchor',restore_observers=True)
                sleep_header=work/'sleep-profile.h'
                sleep_guards=','.join('{'+g['address']+'u,'+str(g['bytes'])+'u,'+digest_initializer(g['sha256'])+'}' for g in sleep_composition['guards'])
                sleep_header.write_text('#define XW_PLAYER_NATIVE_SLEEP\n#define XW_NATIVE_SLEEP_GUARDS {'+sleep_guards+'}\n')
                rf_header.write_text(rf_header.read_text()+'#include "'+str(sleep_header)+'"\n')
    stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
    if hashlib.sha256(stock).hexdigest()!=STOCK_SHA:raise ValueError('Pinned Japanese1.11 image required')
    composition=None;settings_visible_count=None
    if native_prepare:
        script='test_builtin_player_composition.py' if builtin_localization else 'test_player_prepare_composition.py'
        with contextlib.redirect_stdout(io.StringIO()):composition=runpy.run_path(str(ROOT/'tools'/script),init_globals={'native_settings_profile':native_remote_settings})
        candidate=composition['artifact'].read_bytes();combined=candidate
        if native_wireless_settings:
            if hashlib.sha256(candidate).hexdigest()!=wireless_composition['base_sha256']:raise ValueError('Wireless base composition changed during build')
            candidate=combined=wireless_candidate
        if builtin_localization:
            edit=composition['owner_edit'];met_edit=composition['met_edit']
            composition['edit']=composition['prepare_edit'];composition['work']=composition['out']
        else:
            edit=composition['composition']['edit'];met_edit=composition['composition']['met_edit']
        if native_remote_settings:
            from native_settings_count import compose as compose_settings_count
            candidate,settings_visible_count=compose_settings_count(candidate,work/'settings-visible-count'/str(time.time_ns()))
            combined=candidate
        output=work/'SpiderApp.player-prepare.analysis-only.elf'
    else:
        candidate,edit=patch_owner_anchor(stock)
        output=work/'SpiderApp.player-anchor.analysis-only.elf'
        from build_player_met_anchor import patch_met_anchor
        combined,met_edit=patch_met_anchor(candidate)
        (work/'SpiderApp.player-met.analysis-only.elf').write_bytes(combined)
    page_inputs=[]
    if native_remote_page_analysis:
        from compose_remote_native_page import compose as compose_page
        page_dir=work/'remote-page'
        page_artifact,page=compose_page(candidate,page_dir)
        candidate=combined=page_artifact.read_bytes()
        header=ROOT/page['guard_profile']
        native_flags+=['-I'+str(header.parent),'-include',str(header)]
        sources+=['runtime/platform/player/'+name+'.c' for name in
                  ('remote_page_adapter','remote_page_guard','remote_page_ports')]
        sources+=['runtime/apps/wireless-remote/'+name+'.c' for name in
                  ('native_choice_view','native_page_bridge')]
        page_inputs=list(page['source_hashes'])+[
            'runtime/apps/wireless-remote/native_choice_view.h',
            'runtime/apps/wireless-remote/native_page_bridge.h',
            page['guard_profile'],(page_dir/'report.json').relative_to(ROOT).as_posix(),
        ]+[resource['artifact'] for resource in page['resource_overlay'].values()]
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_LIBC_CLOCK',*(['-DXW_PLAYER_ENGINE_PROVIDER'] if engine_provider else []),*(['-DXW_PLAYER_NATIVE_PREPARE','-DXW_PLAYER_CAPTURE_ARG2'] if native_prepare else []),*native_flags,'-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-fvisibility=hidden','-fno-builtin','-fno-stack-protector','-nostdlib','-shared','-Wl,--hash-style=sysv,--build-id=none,-z,defs',*sources,str(extra/'libdl.so.2'),str(extra/'libpthread.so.0'),str(ROOT/'work/stock-resolver-probe/librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(library)],cwd=ROOT,check=True)
    output.write_bytes(candidate)
    dso=ELFFile(io.BytesIO(library.read_bytes()))
    needed=[tag.needed for tag in dso.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_NEEDED']
    inputs=sorted(set(sources+['tools/build_player_host.py','tools/build_player_met_anchor.py','runtime/native/sha256.h','runtime/store/deadline.h']+[p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/player').glob('*.h')]))
    if composition:inputs += [composition['artifact'].relative_to(ROOT).as_posix(),(composition['work']/'report.json').relative_to(ROOT).as_posix(),'tools/player_prepare_bridge.py','tools/test_player_prepare_composition.py']
    if builtin_localization:
        inputs+=['tools/test_builtin_player_composition.py','tools/builtin_language.py']
        inputs+=list(composition['home_report']['source_hashes'])
    if native_remote_settings:inputs+=list(composition['settings_composition']['report']['source_hashes'])
    if settings_visible_count:inputs+=list(settings_visible_count['source_hashes'])
    if native_remote_settings:inputs+=['runtime/apps/wireless-remote/settings_backend.h','runtime/apps/wireless-remote/supervisor_process.h','runtime/platform/wireless/mode.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h','runtime/store/target_abi.h']
    if native_rf_gate and native_remote_settings:inputs+=['runtime/apps/wireless-remote/settings_factory.h']
    if factory_profile:inputs+=[factory_profile['review'],factory_profile['supervisor_artifact'],'runtime/platform/player/remote_ready.h']
    if native_wireless_settings:inputs+=list(wireless_composition['source_hashes'])+['runtime/platform/wireless/native_setting.h','runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h']
    if native_rf_gate:inputs+=list(rf_composition['source_hashes'])+[p.relative_to(ROOT).as_posix() for p in (ROOT/'runtime/platform/wireless').glob('*.h')]+['runtime/store/target_abi.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h']
    if sleep_composition:inputs+=list(sleep_composition['source_hashes'])
    inputs+=page_inputs
    report=dict(passed=True,analysis_only=True,ready_to_flash=False,firmware_package_created=False,device_accessed=False,
        stock_sha256=STOCK_SHA,candidate_sha256=hashlib.sha256(candidate).hexdigest(),candidate_growth_bytes=len(candidate)-len(stock),engine_provider=engine_provider,managed_host=managed_host,legacy_listener=not managed_host,native_prepare=native_prepare,
        library_bytes=library.stat().st_size,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),needed=needed,
        play_mode_read_supported=bool(managed_host and native_prepare),play_mode_control_operation=5,
        localization_profile='builtin-language' if builtin_localization else 'legacy',
        native_remote_settings_request_bridge=native_remote_settings,settings_visible_count_composition=settings_visible_count,remote_activation_backend_compiled=native_remote_settings,remote_activation_backend_installed=False,remote_factory_compiled=bool(native_rf_gate and native_remote_settings),remote_factory_automatic=bool(factory_profile),remote_factory_profile=factory_profile,
        native_wireless_settings_request_bridge=native_wireless_settings,wireless_composition=wireless_composition,wireless_authority_installed=False,
        native_rf_gate=native_rf_gate,rf_composition=rf_composition,rf_worker_provisioned=False,
        rf_worker_entry_composed=native_rf_gate,rf_delivery_bootstrap_compiled=native_rf_gate,rf_delivery_published=False,
        rf_publisher_compiled=native_rf_gate,rf_owner_tick_installed=native_rf_gate,rf_original_queue_publishes=False,
        rf_original_queue_calls_publisher=native_rf_gate,rf_authority_bootstrapped=False,rf_native_retirement_bound=False,
        rf_boot_probe_compiled=native_rf_gate,rf_authority_autobind_compiled=native_rf_gate,
        rf_early_demand_coalesced=native_rf_gate,rf_initial_offer_wait_compiled=native_rf_gate,
        rf_poweroff_observer_composed=native_rf_gate,rf_retirement_receipt_compiled=native_rf_gate,
        rf_native_stop_compiled=native_rf_gate,rf_disable_checkpoint_composed=native_rf_gate,
        library_bss_bytes=int(dso.get_section_by_name('.bss')['sh_size']),
        library_load_file_bytes=sum(int(s['p_filesz']) for s in dso.iter_segments() if s['p_type']=='PT_LOAD'),
        library_load_memory_bytes=sum(int(s['p_memsz']) for s in dso.iter_segments() if s['p_type']=='PT_LOAD'),
        edit=edit,met_edit=met_edit,combined_sha256=hashlib.sha256(combined).hexdigest(),combined_growth_bytes=len(combined)-len(stock),
        source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in inputs},
        limits=['No preload/boot integration is installed or included in a firmware package.','The DSO contains the local endpoint and experimental native-Moma metadata/default-track and FORMAT3 playlist-prototype workers; playlist semantics, queue and physical runtime qualification remain incomplete.','PID/anchor, native ABI and host-worker fixtures are separate evidence; Sony worker creation, resource handoff and hardware are unqualified.'])
    if engine_provider:report['limits'].append('Explicit engine-provider analysis profile only: original owner/lifetime, managed grants, deferred teardown, post-handoff control and real playback remain unqualified; not ready to install.')
    if managed_host:report['limits'].append('Managed profile has one caller-owned session workspace and no automatic listener/authorization source. Trusted descriptor offer and native exit hooks remain uninstalled; no physical service qualification.')
    if composition:report.update(prepare_edit=composition['edit'],prepare_bridge_growth_bytes=0,source_composition_report=str((composition['work']/'report.json').relative_to(ROOT)))
    if native_prepare:report['limits'].append('Explicit native-prepare analysis pairing only; original manager descriptor delivery, complete intervening-event ordering, loader/hardware acceptance and recovery remain unqualified. No firmware activation.')
    report['native_sleep_analysis']=native_sleep_analysis
    if native_remote_page_analysis:
        report['native_remote_page_analysis']=(page_dir/'report.json').relative_to(ROOT).as_posix()
        report['limits'].append('Native Remote page and private adapter are paired for offline analysis. Wi-Fi reentry and physical renderer ordering remain unqualified.')
    if sleep_composition:
        report['sleep_composition']=sleep_composition
        report['limits'].append('Native sleep/recovery analysis only; physical timing and hardware qualification remain incomplete. Not enabled by firmware packaging.')
    (work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    return library,output,report
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--engine-provider',action='store_true')
    parser.add_argument('--native-sleep-analysis',action='store_true',help='Offline native sleep/recovery composition; no hardware qualification or installation')
    parser.add_argument('--managed-host',action='store_true');parser.add_argument('--native-prepare',action='store_true');parser.add_argument('--builtin-localization',action='store_true');parser.add_argument('--native-remote-settings',action='store_true');parser.add_argument('--native-wireless-settings',action='store_true');parser.add_argument('--native-rf-gate',action='store_true');parser.add_argument('--remote-profile',type=Path)
    parser.add_argument('--review-output',type=Path,help='New private output directory; preserve earlier artifacts')
    parser.add_argument('--native-remote-page-analysis',action='store_true',help='Pair the native Remote page and host DSO for offline analysis')
    # Parse after all options are registered.
    options=parser.parse_args()
    _,_,report=build(engine_provider=options.engine_provider,managed_host=options.managed_host,native_prepare=options.native_prepare,builtin_localization=options.builtin_localization,native_remote_settings=options.native_remote_settings,native_wireless_settings=options.native_wireless_settings,native_rf_gate=options.native_rf_gate,remote_profile=options.remote_profile,native_sleep_analysis=options.native_sleep_analysis,review_output=options.review_output,native_remote_page_analysis=options.native_remote_page_analysis);print(json.dumps(report,indent=2))
