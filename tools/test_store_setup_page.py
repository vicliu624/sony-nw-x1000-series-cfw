"""Verify the setup guidance rendered by the selected actual store ELF."""
from pathlib import Path
import argparse,hashlib,json,os,re
from workflow_paths import composition_path,work_area,evidence_path,write_report
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--profile',default='store-setup');parser.add_argument('--composition',default='work/store-setup-workflow-fixture');options=parser.parse_args();os.environ['HB_WORKFLOW_PROFILE']=options.profile;os.environ['HB_WORKFLOW_COMPOSITION']=options.composition
source=evidence_path(ROOT,'native-libc-production-store-loop-tests.json');result=verify_report(ROOT,str(source.relative_to(ROOT)));assert result['passed'] and result['exit']==0
composition=composition_path(ROOT);store=composition/'external/HOMEBREW/apps/store/app';assert hashlib.sha256(store.read_bytes()).hexdigest()==result['unchanged_store_sha256']
work=work_area(ROOT,'libc-production-store-loop-review');frame=work/'store.rgb565';raw=frame.read_bytes();assert len(raw)==240*432*2
font=ROOT/'runtime/native/font.inc';glyphs=[list(map(int,row.split(','))) for row in re.findall(r'\{([0-9,]+)\}',font.read_text())]
for x,y,scale,text in ((12,96,2,'SETUP NEEDED'),(12,150,1,'REPOSITORY FILES ARE MISSING'),(8,404,2,'BACK')):
 for n,ch in enumerate(text):
  glyph=[0]*7 if ch==' ' else glyphs[ord(ch)-ord('A')+10]
  for row in range(7):
   for column in range(5):
    offset=((y+row*scale)*240+x+n*6*scale+column*scale)*2
    assert (int.from_bytes(raw[offset:offset+2],'little')==0xffff)==bool(glyph[row]&(1<<(4-column)))
tracked=[Path(__file__),source,frame,work/'store.png',font,store]
report={'passed':True,'actual_store_setup_page_verified':True,'BACK_exit':0,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['Actual ELF frame captured through virtual framebuffer/touch, not physical screen.','Loader and lifecycle tests separately check error classification and absence of remote-store calls.']}
write_report(ROOT,'native-store-setup-page-tests.json',report);print('Actual selected store: setup title, missing-files guidance and BACK frame verified.')
