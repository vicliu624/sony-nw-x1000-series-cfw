"""Build an analysis-only owner-loop DSO and one-instruction ELF candidate."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
CORE_SOURCES=['runtime/platform/player/host_hook.c','runtime/platform/player/host_pid.S','runtime/platform/player/client.c','runtime/platform/player/stock_provider.c','runtime/platform/player/stock_info.c','runtime/platform/player/local_identity.c','runtime/platform/player/stock_gui.c','runtime/platform/player/stock_volume.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c']
SOURCES=CORE_SOURCES+['runtime/platform/player/stock_source.c','runtime/platform/player/host_service.c','runtime/platform/player/host_queue.c','runtime/platform/player/rpc_wire.c','runtime/platform/player/rpc_posix.c','runtime/platform/player/stock_media.c','runtime/platform/player/stock_query.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/media_text.c','runtime/platform/player/metadata_async.c','runtime/platform/player/audio_check_async.c','runtime/platform/player/stock_queue_owner.c','runtime/platform/player/queue_capture.c','runtime/platform/player/queue_exchange.c','runtime/platform/player/queue_browser.c','runtime/platform/player/queue_page.c','runtime/platform/player/group_reader.c','runtime/platform/player/group_native.c','runtime/platform/player/queue_async.c','runtime/platform/player/player_broker.c','runtime/store/deadline.c']
STOCK_SHA='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
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

def build():
    work=ROOT/'work/player-host';work.mkdir(exist_ok=True)
    lib=ROOT/'work/arm-signal-tests/lib';extra=ROOT/'work/player-sqlite-ro'
    library=work/'libx1000-player-analysis.so'
    subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-DHB_STORE_LIBC_CLOCK','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-fvisibility=hidden','-fno-builtin','-fno-stack-protector','-nostdlib','-shared','-Wl,--hash-style=sysv,--build-id=none,-z,defs',*SOURCES,str(extra/'libdl.so.2'),str(extra/'libpthread.so.0'),str(ROOT/'work/stock-resolver-probe/librt.so.1'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(library)],cwd=ROOT,check=True)
    stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
    if hashlib.sha256(stock).hexdigest()!=STOCK_SHA:raise ValueError('Pinned Japanese1.11 image required')
    candidate,edit=patch_owner_anchor(stock)
    output=work/'SpiderApp.player-anchor.analysis-only.elf';output.write_bytes(candidate)
    from build_player_met_anchor import patch_met_anchor
    combined,met_edit=patch_met_anchor(candidate)
    (work/'SpiderApp.player-met.analysis-only.elf').write_bytes(combined)
    dso=ELFFile(io.BytesIO(library.read_bytes()))
    needed=[tag.needed for tag in dso.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_NEEDED']
    report=dict(passed=True,analysis_only=True,ready_to_flash=False,firmware_package_created=False,device_accessed=False,
        stock_sha256=STOCK_SHA,candidate_sha256=hashlib.sha256(candidate).hexdigest(),candidate_growth_bytes=0,
        library_bytes=library.stat().st_size,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),needed=needed,
        library_bss_bytes=int(dso.get_section_by_name('.bss')['sh_size']),
        library_load_file_bytes=sum(int(s['p_filesz']) for s in dso.iter_segments() if s['p_type']=='PT_LOAD'),
        library_load_memory_bytes=sum(int(s['p_memsz']) for s in dso.iter_segments() if s['p_type']=='PT_LOAD'),
        edit=edit,met_edit=met_edit,combined_sha256=hashlib.sha256(combined).hexdigest(),combined_growth_bytes=len(combined)-len(stock),
        source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES+['tools/build_player_host.py','tools/build_player_met_anchor.py','runtime/platform/player/session_identity.h','runtime/platform/player/host_queue.h']},
        limits=['No preload/boot integration is installed or included in a firmware package.','The DSO contains the local endpoint and experimental native-Moma metadata/default-track and FORMAT3 playlist-prototype workers; playlist semantics, queue and physical runtime qualification remain incomplete.','PID/anchor, native ABI and host-worker fixtures are separate evidence; Sony worker creation, resource handoff and hardware are unqualified.'])
    (work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    return library,output,report
if __name__=='__main__':
    _,_,report=build();print(json.dumps(report,indent=2))
