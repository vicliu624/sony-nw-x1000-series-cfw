"""ARM literal references to pinned music-import diagnostic strings, static only."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
def at(va,n):
    for s in segments:
        if s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz']:
            p=s['p_offset']+va-s['p_vaddr'];return raw[p:p+n]
    return None
targets={0x4b0898:'omg_id3_v2_valid_header',0x4b09c8:'unsupported ID3 version',
         0x4affec:'omg_id3_v2_tag_header_parse',0x412a5c:'SearchRebuildNtfyDbOpen',
         0x496fbc:'/contents/OMGAUDIO'}
rows=[]
for segment in segments:
    if not segment['p_flags']&1:continue
    data=segment.data();base=segment['p_vaddr']
    for offset in range(0,len(data)-3,4):
        ins=struct.unpack_from('<I',data,offset)[0]
        if ins&0x0f7f0000!=0x051f0000:continue
        pc=base+offset;pool=pc+8+(1 if ins&0x800000 else -1)*(ins&4095)
        word=at(pool,4)
        if word is None:continue
        target=struct.unpack('<I',word)[0]
        if target not in targets:continue
        start=max(base,pc-80)
        window=subprocess.run(['arm-linux-gnueabi-objdump','-d','--start-address='+str(start),'--stop-address='+str(start+200),str(ROOT/'work/targets-jp/SpiderApp')],capture_output=True,text=True,check=True).stdout.splitlines()
        rows.append({'target':hex(target),'meaning':targets[target],'reference':hex(pc),
                     'literal_pool':hex(pool),'window':window})
report={'scope':'static ARM literal references, not function or runtime qualification',
        'input_sha256':hashlib.sha256(raw).hexdigest(),'references':rows,'device_access':False,
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'sources/native-stock-music-import-xrefs.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:
 print(r['meaning'],r['reference']);print('\n'.join(r['window']))
