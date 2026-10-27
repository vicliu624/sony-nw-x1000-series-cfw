"""Compare a stock OMF channel request to the GPL ARM ABI; no driver execution."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/interdsp-interface-review'
header=work/'include_asm-arm_arch-mp200_inter_dsp_ioctl.h'
driver=work/'arch_arm_mach-mp200_inter_dsp.c'
library=ROOT/'work/stock-manager-runtime-probe/root/usr/lib/omf/libomf_core_hw_dep.so'
packed=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
with tarfile.open(packed,'r:gz') as archive:
    assert header.read_bytes()==archive.extractfile('./include/asm-arm/arch-mp200/inter_dsp_ioctl.h').read()
    assert driver.read_bytes()==archive.extractfile('./arch/arm/mach-mp200/inter_dsp.c').read()
probe=work/'abi.c';obj=work/'abi.o'
probe.write_text('#include "'+header.name+'"\nconst unsigned evidence[]={sizeof(void*),sizeof(struct dsp_cmd_ch),INTERDSP_SET_CHINFO,INTERDSP_GET_CHINFO,INTERDSP_WAITCH,INTERDSP_DOWNLOAD};\n')
subprocess.run(['arm-linux-gnueabi-gcc','-march=armv5te','-marm','-c',str(probe),'-o',str(obj)],check=True)
elf=ELFFile(io.BytesIO(obj.read_bytes()));values=struct.unpack('<6I',elf.get_section_by_name('.rodata').data())
assert values[:3]==(4,24,0x40184411)
target=ELFFile(io.BytesIO(library.read_bytes()))
def instruction(address):
    segment=next(p for p in target.iter_segments() if p['p_type']=='PT_LOAD' and p['p_vaddr']<=address<p['p_vaddr']+p['p_filesz'])
    return struct.unpack_from('<I',segment.data(),address-segment['p_vaddr'])[0]
def immediate(word):
    value=word&255;rotate=((word>>8)&15)*2
    return ((value>>rotate)|(value<<(32-rotate)))&0xffffffff if rotate else value
command=0;words=[]
for address,opcode in ((0x2488,13),(0x2490,4),(0x24a8,4)):
    word=instruction(address);assert word&(1<<25) and (word>>21)&15==opcode and (word>>12)&15==1
    if opcode==13:command=immediate(word)
    else:assert (word>>16)&15==1;command=(command+immediate(word))&0xffffffff
    words.append({'address':hex(address),'instruction':hex(word)})
assert command==values[2]
source=driver.read_text(errors='replace')
for marker in ('request_irq(INT_DSP','interdsp_wait_ack','atomic_read(&sq->ack)','interdsp_download','dsp_ires(1)'):
    assert marker in source
tracked=[Path(__file__),header,driver,library,packed,probe,obj]
report={'scope':'Static GPL/stock OMF ABI comparison only; not DSP execution or a mock driver',
        'pointer_bytes':values[0],'channel_struct_bytes':values[1],
        'ioctls':dict(zip(('set_channel','get_channel','wait_channel','download'),map(hex,values[2:]))),
        'stock_command_instructions':words,'stock_set_channel_matches_header':True,
        'observed_runtime_limit':'Stock GUI stops before driver open succeeds; channel requests were not executed in that run.',
        'source_driver_boundaries':['DSP-specific IRQ registration','ACK wait queue and timeout','firmware download/reset/clock controls'],
        'runtime_dsp_initialized':False,'hardware_tested':False,
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(ROOT/'sources/native-interdsp-interface-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','stock_command_instructions')},indent=2))
