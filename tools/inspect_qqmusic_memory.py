"""ARM layout/static budget audit. This is not a physical-device RSS profile."""
from pathlib import Path
import json,re,struct,subprocess
from elftools.elf.elffile import ELFFile
from qqmusic_font_config import FONT_BYTES
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-memory';work.mkdir(exist_ok=True)
volume=(ROOT/'runtime/apps/qqmusic/qqmusic_volume.c').read_text();ui=(ROOT/'runtime/apps/qqmusic/qqmusic_ui.c').read_text()
observation=re.search(r'struct observation \{.*?\};',volume,re.S).group()
glyph=re.search(r'struct glyph_cache \{.*?\};',ui,re.S).group()
program=re.search(r'struct program \{.*?\};',(ROOT/'runtime/apps/qqmusic/qqmusic_program.c').read_text(),re.S).group()
code='#include "runtime/apps/qqmusic/qqmusic_network.h"\n#include "runtime/apps/qqmusic/qqmusic_image.h"\n#include "runtime/apps/qqmusic/qqmusic_import_binding.h"\n#include "runtime/apps/qqmusic/qqmusic_program.h"\n#include "runtime/apps/qqmusic/qqmusic_identity.h"\n#define QQ_VOLUME_PREFIX_LIMIT 16u\n'+observation+'\n'+glyph+'\n'+program+'\nconst unsigned qq_memory_sizes[]={sizeof(struct observation),sizeof(struct glyph_cache)*64,QQ_UI_PIXELS*2,QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE*2,sizeof(struct qq_runtime),sizeof(struct qq_network),sizeof(struct qq_import_binding),sizeof(struct program)};\n'
(work/'layout.c').write_text(code)
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-march=armv5te','-marm','-mfloat-abi=soft','-I'+str(ROOT),'-I'+str(ROOT/'work/stock-resolver-probe'),'-I'+str(ROOT/'work/external-tls-probe/bearssl-0.6/inc'),'-c',str(work/'layout.c'),'-o',str(work/'layout.o')],check=True)
with open(work/'layout.o','rb') as f:
 elf=ELFFile(f);symbol=next(s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name=='qq_memory_sizes');data=elf.get_section(symbol['st_shndx']).data();values=struct.unpack('<8I',data[symbol['st_value']:symbol['st_value']+32])
names=['volume_observer_transient','glyph_cache','ui_canvas','qr_pixels','runtime_struct','network_struct','import_binding_struct','program_struct']
trace=(ROOT/'work/qqmusic-device-full-check/mapped-font.trace').read_text()
assert any(str(FONT_BYTES) in line and 'PROT_READ,MAP_PRIVATE' in line for line in trace.splitlines() if 'mmap' in line)
report={'scope':'ARM static structures and explicit buffer bounds; not hardware peak RSS','arm_bytes':dict(zip(names,values)),'font':{'file_bytes':FONT_BYTES,'font_sized_anonymous_heap_allocation':False,'mapping':'read-only MAP_PRIVATE from verified user file','streaming_hash_buffer':4096,'second_full_mapping_hash':False,'kernel_file_cache_still_uses_reclaimable_RAM':True},'savings':{'glyph_cache_bytes':values[1],'volume_observer_bytes':48*(24+8+2049)},'jpeg_decoded_output_bytes_per_pixel':3,'jpeg_previous_decoded_output_bytes_per_pixel':4,'png_alpha_still_preserved':True,'audio_pcm_buffer_bytes':2304*2,'network_response_body_bound':262144,'artwork_output_bound':524288,'image_heap_limit':16777216,'limits':['mmap is not zero RAM; source verification reads all bytes and can warm reclaimable page cache.','Ogg/Tremor/Shine and image-decoder working sets remain workload dependent; physical X1060 available-memory/peak/CPU figures are not measured.','No storage guard weakened, no account/login/network test performed.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
