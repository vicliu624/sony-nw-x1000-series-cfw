"""Inspect a live native popup's cached image before teardown, PC only."""
from pathlib import Path
import argparse,hashlib,json,struct,sys,zlib,binascii
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--prepare-cache',action='store_true');parser.add_argument('--instruction-budget',type=int,default=20000000);args=parser.parse_args()
harness=ROOT/'tools/debug/probe_home_feedback_popup.py';source=harness.read_text();marker='destroyed=call(0xc6a20'
assert source.count(marker)==1
# This is a debugger stop before destruction; no harness source is modified.
namespace={'__file__':str(harness),'__name__':'__main__'}
previous=sys.argv;sys.argv=[str(harness),'--message','homebrew','--native-image-manager','--output',args.output,'--instruction-budget',str(args.instruction_budget)]
try:exec(compile(source.split(marker,1)[0],str(harness),'exec'),namespace)
finally:sys.argv=previous
(namespace['out']/'prefix-status.json').write_text(json.dumps({key:namespace.get(key) for key in ['creation_and_frame_passed','stop','created','shown','frame_updated','commit_ok']},indent=2)+'\n')
assert namespace['creation_and_frame_passed'] and not namespace['stop'],namespace['stop']
u=namespace['u'];word=namespace['word'];text=namespace['text_control'];out=namespace['out'];assert word(text+0xae4)==12
prepared=namespace['call'](0xe91c4,[namespace['manager'],0,0,0]) if args.prepare_cache else None
(out/'preparation.json').write_text(json.dumps({'result':prepared,'stop':namespace['stop']},indent=2)+'\n')
assert not namespace['stop'],namespace['stop']
info=bytes(u.mem_read(text+0xaf8,352));frame=struct.unpack('<88I',info);(out/'text-frame-info.bin').write_bytes(info)
assert frame[0]==2
lookup=0x5001f000;result=namespace['call'](0x132fd0,[frame[4],lookup,0,0]);assert result['stopped_at_expected'] and result['r0']==0
header_pointer=word(lookup);header=bytes(u.mem_read(header_pointer,64));fields=struct.unpack('<16I',header);(out/'bitmap-header.bin').write_bytes(header)
report={'scope':'Native popup cached-image inspection, with optional original cache preparation; no direct glyph draw call','cache_preparation_completed':bool(prepared and prepared['stopped_at_expected'] and not namespace['stop']),'native_cache_prepared':prepared,'image_handle':frame[4],'frame_info_first_words':list(frame[:12]),'bitmap_header_pointer':hex(header_pointer),'bitmap_header_words':list(fields),'candidate_upg_sha256':hashlib.sha256(namespace['package']).hexdigest(),'harness_sha256':hashlib.sha256(harness.read_bytes()).hexdigest(),'capture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'physical_display_verified':False}
width,height,flags=fields[:3]
if flags&8 and 0<width<=2048 and 0<height<=2048:
 pixels=bytes(u.mem_read(fields[6],width*height*3));(out/'bitmap-plane.bin').write_bytes(pixels)
 report.update({'width':width,'height':height,'format_flags':hex(flags),'plane_pointer':hex(fields[6]),'nonzero_bytes':sum(v!=0 for v in pixels),'plane_sha256':hashlib.sha256(pixels).hexdigest(),'rgb_channel_order_qualified':False})
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
 scanlines=b''.join(b'\0'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
 (out/'bitmap-plane.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scanlines))+chunk(b'IEND',b''))
(out/'capture.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
