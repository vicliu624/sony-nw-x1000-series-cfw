"""Trace stock root reactivation event to command7, intercepting only coordinator boundary."""
import runpy,struct,json
from pathlib import Path
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')))
g=n['hook'].__globals__;g['intercept_actions']=False;g['deactivate_probe']=True
u=n['u'];rows=[]
for state in (1,2,3,4,5):
 context=bytearray(32);context[0]=2;context[1]=state;context[13]=10
 struct.pack_into('<I',context,4,0x3f4f18)
 u.mem_write(0x60010000,bytes(context));g['deactivate_commands'].clear()
 assert n['call'](0x17c608,(0x60010000,0x420023,0,0))==0
 calls=g['deactivate_commands'].copy()
 assert calls==([] if state==2 else [[0x613e60,7]]),calls
 rows.append({'mode_fixture':2,'state_fixture':state,'event':'0x420023','coordinator_calls':calls})
r={'scope':'Original root dispatcher and selected action execute continuously; coordinator intercepted','SpiderApp_sha256':n['digest'],'cases':rows,'limits':['Root states are supplied, not reached by a full APF transport session.','Coordinator execution and GUI restore selection are separately checked, not one integrated lifecycle.']}
Path(n['ROOT'],'sources/native-reactivation-command7.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(rows,indent=2))
