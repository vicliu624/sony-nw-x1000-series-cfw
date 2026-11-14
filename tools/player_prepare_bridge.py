"""Compose the pinned Japanese 1.11 player prepare bridge offline."""
import struct
import hashlib
import io
import json
import re
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_player_met_anchor import branch, patch_met_anchor
PREPARE_BRIDGE=0x4d7fc0
PREPARE_HANDLED=0x58575052
PREPARE_COMPOSITION_SHA='ab2b31b56b4b70c793491f3a33fa4edbee8ab337b0794389abc61db168551e61'
BUILTIN_COMPOSITION_SHA='a207541d1099e5d470fa094f438723c3f3743b1db999720fbb446340c196f530'
REMOTE_SETTINGS_COMPOSITION_SHA='97a3f8dfe64743431db98de0668b6a52f1967cedf68ece79b6d2137ce4b82f23'


def prepare_bridge(address=PREPARE_BRIDGE):
    if address!=PREPARE_BRIDGE:
        raise ValueError('Only the planned analysis address is supported')
    # Save native arguments/LR. Ordinary PID/failure results restore the exact
    # arguments and tail-call original prepare. Only the explicit handled marker
    # restores the caller and returns0 without entering original prepare.
    # Non-marker means permission for original cleanup, NOT a generic safe
    # error path. An owning/faulted SDK dispatcher must suppress cleanup until
    # its resource policy is satisfied. This byte generator supplies no policy.
    return struct.pack('<11I',0xe92d500f,branch(address+4,0xda84,True),
                       0xe59fc018,0xe150000c,0x0a000001,0xe8bd500f,
                       branch(address+24,0x112fc,False),0xe8bd500f,
                       0xe3a00000,0xe12fff1e,PREPARE_HANDLED)


def patch_prepare_bridge(raw,original,*,profile='external-language'):
    """Patch only a source-composed analysis ELF with an existing mapped slot.

    No DSO dispatcher, authorization/lifetime policy or installer is enabled.
    """
    stock_hash='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
    if hashlib.sha256(original).hexdigest()!=stock_hash:
        raise ValueError('Pinned original Japanese1.11 image required')
    image=ELFFile(io.BytesIO(raw));stock=ELFFile(io.BytesIO(original))
    if image.elfclass!=32 or not image.little_endian or image['e_machine']!='EM_ARM' or image['e_type']!='ET_EXEC':
        raise ValueError('Expected fixed-address ARM32 executable')

    def at(elf,address,count,executable=False):
        segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']]
        if len(segments)!=1 or (executable and not segments[0]['p_flags']&1):
            raise ValueError('Range is not uniquely mapped with required permissions')
        s=segments[0]
        return int(s['p_offset']+address-s['p_vaddr'])

    spans=[]
    for address,count in ((0x112fc,0x378),(0x718c0,0x30),(0x71a3c,0x88),(0xda84,12)):
        location=at(image,address,count,True);baseline=at(stock,address,count,True)
        if raw[location:location+count]!=original[baseline:baseline+count]:
            raise ValueError('Original prepare/action/PID span mismatch')
        spans.append(dict(address=hex(address),bytes=count,sha256=hashlib.sha256(raw[location:location+count]).hexdigest()))
    bridge=prepare_bridge();slot=at(image,PREPARE_BRIDGE,len(bridge),True)
    if raw[slot:slot+len(bridge)]!=bytes(len(bridge)):
        raise ValueError('Planned prepare bridge slot occupied')
    profiles={'external-language':PREPARE_COMPOSITION_SHA,
              'builtin-language':BUILTIN_COMPOSITION_SHA,
              'native-settings':REMOTE_SETTINGS_COMPOSITION_SHA}
    if profile not in profiles or hashlib.sha256(raw).hexdigest()!=profiles[profile]:
        raise ValueError('Source composition profile mismatch')
    result=bytearray(raw);result[slot:slot+len(bridge)]=bridge;sites=[]
    for address in (0x718e0,0x71aa4):
        location=at(image,address,4,True)
        if struct.unpack_from('<I',raw,location)[0]!=branch(address,0x112fc,True):
            raise ValueError('Unexpected original prepare call')
        struct.pack_into('<I',result,location,branch(address,PREPARE_BRIDGE,True));sites.append(hex(address))
    check=ELFFile(io.BytesIO(result))
    if check.header!=image.header or [dict(s.header) for s in check.iter_segments()]!=[dict(s.header) for s in image.iter_segments()]:
        raise ValueError('ELF headers changed')
    return bytes(result),dict(analysis_only=True,ready_to_flash=False,additional_elf_bytes=0,
                             stub=hex(PREPARE_BRIDGE),stub_bytes=len(bridge),callsites=sites,
                             original_spans=spans,stock_sha256=stock_hash)


def check_stock_spans(owner):
    native_guards = []
    elf = ELFFile(io.BytesIO(owner))
    loads = [segment for segment in elf.iter_segments() if segment['p_type'] == 'PT_LOAD']
    for path in sorted((ROOT / 'runtime/platform/player').glob('stock_*.c')):
        name = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        arrays = [(match.start(), match[1], bytes(int(value, 16) for value in
                   re.findall(r'0x([0-9a-fA-F]+)', match[2])))
                  for match in re.finditer(r'(\w+)\[32\]\s*=\s*\{([^}]+)\}', source)]
        calls = [(*match.groups(), match.start()) for match in re.finditer(
            r'xw_stock_image_match\(\s*(0x[0-9a-fA-F]+)u?\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*(\w+)\s*\)', source)]
        if path.name == 'stock_volume.c':
            constants = dict(re.findall(r'#define\s+(REGION_\w+)\s+(0x[0-9a-fA-F]+)u?', source))
            count = int(constants['REGION_END'], 16) - int(constants['REGION_BEGIN'], 16)
            calls.append((constants['REGION_BEGIN'], hex(count), 'expected', len(source)))
        for address, length, identifier, position in calls:
            expected = next(value for start, symbol, value in reversed(arrays)
                            if symbol == identifier and start < position)
            start, count = int(address, 16), int(length, 16)
            mappings = [segment for segment in loads if segment['p_vaddr'] <= start
                        and start + count <= segment['p_vaddr'] + segment['p_filesz']]
            if len(mappings) != 1:
                raise ValueError(f'Expected one stock guard mapping at {address}')
            segment = mappings[0]
            offset = segment['p_offset'] + start - segment['p_vaddr']
            if hashlib.sha256(owner[offset:offset + count]).digest() != expected:
                raise ValueError(f'Stock guard mismatch in {name} at {address}')
            native_guards.append(dict(source=name, address=address, bytes=count, digest=identifier))
    if len(native_guards) < 17:
        raise ValueError('Missing stock player guards')
    return native_guards


def build_builtin(out, stock, *, native_settings=False):
    from build_home_feedback import build as build_home
    from build_player_host import patch_owner_anchor
    from builtin_language import enable_home_settings

    out.mkdir(parents=True)
    sources = ['tools/player_prepare_bridge.py', 'tools/builtin_language.py',
               'tools/build_player_host.py', 'tools/build_player_met_anchor.py']
    resource_review = None
    if native_settings:
        from prepare_remote_settings_row import build as build_settings
        settings_dir = out / 'settings'
        _, settings_artifact, settings_report = build_settings(settings_dir)
        base = settings_artifact.read_bytes()
        profile = 'native-settings'
        home_sources = settings_report['home_source_hashes']
        sources.extend(settings_report['source_hashes'])
        resource_review = (settings_dir / 'report.json').relative_to(ROOT).as_posix()
    else:
        home, symbols, home_report = build_home(out / 'home')
        base = enable_home_settings(home, symbols)
        profile = 'builtin-language'
        home_sources = home_report['source_hashes']
    sources.extend(home_sources)

    owner, owner_edit = patch_owner_anchor(base)
    guards = check_stock_spans(owner)
    sources.extend(path.relative_to(ROOT).as_posix()
                   for path in (ROOT / 'runtime/platform/player').glob('stock_*.c'))
    native_guards = [{key: row[key] for key in ('source', 'address', 'bytes')} for row in guards]
    met, met_edit = patch_met_anchor(owner, mapped_stub=0x4d7ff0)
    candidate, prepare_edit = patch_prepare_bridge(met, stock, profile=profile)
    artifact = out / 'SpiderApp.builtin-player-met.analysis-only.elf'
    artifact.write_bytes(candidate)
    report = dict(analysis_only=True, ready_to_flash=False, device_accessed=False,
                  firmware_package_created=False, native_settings_profile=native_settings,
                  base_sha256=hashlib.sha256(base).hexdigest(),
                  candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                  artifact=artifact.relative_to(ROOT).as_posix(), elf_growth_bytes=len(candidate) - len(base),
                  settings_resource_review=resource_review, owner_edit=owner_edit, met_edit=met_edit,
                  prepare_edit=prepare_edit, home_source_hashes=home_sources, native_guards=native_guards,
                  source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in sorted(set(sources))})
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return base, artifact, report


def build_external_language(out):
    """Build the legacy Homebrew language cache and the player owner/Met anchors."""
    from build_home_feedback import build as build_home
    from build_player_host import patch_owner_anchor
    from builtin_language import normalize_home_feedback
    from release_firmware import add_language_cache

    out.mkdir(parents=True)
    home, symbols, home_report = build_home(out / 'home')
    base = add_language_cache(normalize_home_feedback(home, symbols), out)
    owner, owner_edit = patch_owner_anchor(base)
    guards = check_stock_spans(owner)
    hook = (ROOT / 'runtime/platform/player/host_hook.c').read_text(encoding='utf-8')
    declaration = re.search(r'\banchor_digest\s*\[\s*32\s*\]\s*=\s*\{([^}]+)\}', hook)
    if declaration is None:
        raise ValueError('Missing literal owner-anchor digest in host_hook.c')
    digest = bytes(int(value, 16) for value in re.findall(r'0x([0-9a-fA-F]+)', declaration[1]))
    elf = ELFFile(io.BytesIO(owner))
    address = int(owner_edit['address'], 16)
    segment = next(segment for segment in elf.iter_segments() if segment['p_type'] == 'PT_LOAD'
                   and segment['p_vaddr'] <= address and address + 8 <= segment['p_vaddr'] + segment['p_filesz'])
    offset = segment['p_offset'] + address - segment['p_vaddr']
    if hashlib.sha256(owner[offset:offset + 8]).digest() != digest:
        raise ValueError('Owner anchor does not match host_hook.c digest')
    met, met_edit = patch_met_anchor(owner, mapped_stub=0x4d7ff0)
    sources = ['tools/player_prepare_bridge.py', 'tools/builtin_language.py',
               'tools/build_player_host.py', 'tools/build_player_met_anchor.py',
               'tools/release_firmware.py', 'runtime/platform/player/host_hook.c',
               'runtime/apps/language/process_cache_entry.S', 'runtime/apps/language/process_cache.c',
               'runtime/apps/language/package.c', 'runtime/apps/language/package.h', 'runtime/native/sha256.c']
    sources.extend(path.relative_to(ROOT).as_posix()
                   for path in (ROOT / 'runtime/platform/player').glob('stock_*.c'))
    report = dict(baseline_sha256=hashlib.sha256(base).hexdigest(),
                  composite_sha256=hashlib.sha256(owner).hexdigest(),
                  combined_sha256=hashlib.sha256(met).hexdigest(),
                  anchor_edit=owner_edit, met_edit=met_edit, native_guard_checks=guards,
                  home_source_hashes=home_report['source_hashes'],
                  source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in sources})
    return base, owner, met, report


def build_external_prepare(out, stock):
    _, _, met, composition = build_external_language(out)
    candidate, edit = patch_prepare_bridge(met, stock)
    artifact = out / 'SpiderApp.prepare-bridge.analysis-only.elf'
    artifact.write_bytes(candidate)
    report = dict(analysis_only=True, ready_to_flash=False, device_accessed=False,
                  firmware_package_created=False, base_sha256=composition['combined_sha256'],
                  candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                  artifact=artifact.relative_to(ROOT).as_posix(),
                  owner_edit=composition['anchor_edit'], met_edit=composition['met_edit'],
                  prepare_edit=edit, native_guard_checks=composition['native_guard_checks'],
                  source_hashes={**composition['source_hashes'], **composition['home_source_hashes']})
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return met, artifact, report
