"""Pinned Sony module initialization symbols, call relocations and ARM listings."""
from pathlib import Path
import hashlib,io,json
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-driver-init';OUT.mkdir(parents=True,exist_ok=True)
path=ROOT/'work/hardware-audit/sd8686.ko';raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69'
elf=ELFFile(io.BytesIO(raw));symbols=elf.get_section_by_name('.symtab');text=elf.get_section_by_name('.text');index=next(i for i,s in enumerate(elf.iter_sections()) if s.name=='.text')
selected=[s for s in symbols.iter_symbols() if s['st_shndx']==index and any(n in s.name for n in ('wlan_init','mac_control','key_material','set_wep','setup_station_hw','PrepareAndSendCommand'))]
dis=Cs(CS_ARCH_ARM,CS_MODE_ARM);rows=[]
for symbol in selected:
    start,size=symbol['st_value'],symbol['st_size'];calls=[]
    for section in elf.iter_sections():
        if section['sh_type']!='SHT_REL' or section['sh_info']!=index:continue
        for relocation in section.iter_relocations():
            if start<=relocation['r_offset']<start+size:calls.append({'offset':hex(relocation['r_offset']),'kind':relocation['r_info_type'],'target':symbols.get_symbol(relocation['r_info_sym']).name})
    listing='\n'.join(f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in dis.disasm(text.data()[start:start+size],start))
    (OUT/(symbol.name+'.arm.txt')).write_text(listing+'\n');rows.append({'name':symbol.name,'offset':hex(start),'bytes':size,'relocations':calls})
report={'module_sha256':digest,'functions':rows,'device_accessed':False};(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'module_sha256':digest,'functions':[{'name':r['name'],'offset':r['offset'],'bytes':r['bytes'],'relocations':len(r['relocations'])} for r in rows],'report':str(OUT/'report.json'),'device_accessed':False},indent=2))
