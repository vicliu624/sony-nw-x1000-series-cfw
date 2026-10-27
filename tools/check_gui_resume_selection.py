"""Enumerate stock GUI dispatch with intercepted actions, never execute handlers."""
import runpy, struct, json
from pathlib import Path
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')))
u=n['u']; call=n['call']; hits=n['hits']; word=n['word']
d=0x3ea1dc
state_count=struct.unpack('<H',u.mem_read(d,2))[0]
event_count=struct.unpack('<H',u.mem_read(d+2,2))[0]
assert (state_count,event_count)==(39,171)
event_table=word(d+16)
events=[(word(event_table+i*8),word(event_table+i*8+4)) for i in range(event_count)]
assert [index for _,index in events]==list(range(event_count))
assert len(set(event for event,_ in events))==event_count
matches=[]; total=0
for state in range(1,state_count+1):
 for event,index in events:
  context=bytearray(32);context[0]=1;context[1]=state;context[13]=10
  struct.pack_into('<I',context,4,0x3ea150)
  u.mem_write(0x60010000,bytes(context));hits.clear()
  call(0x17c608,(0x60010000,event,0,0));total+=1
  if 0x5cfb4 in hits:
   matches.append({'state_fixture':state,'event':hex(event),'event_index':index,'selected_actions':[hex(x) for x in hits]})
report={'scope':'Original dispatcher selection only; actions intercepted; state contexts fixtures','SpiderApp_sha256':n['digest'],'cases':total,'state_count':state_count,'event_count':event_count,'restore_callback':'0x5cfb4','matches':matches,'limits':['Does not prove these events are queued during APF restoration.','Does not execute page reconstruction or qualify hardware return.']}
Path(n['ROOT'],'sources/native-gui-resume-selection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

# Execute the stock producer and synchronous bridge, rather than injecting an event.
u.mem_write(0x68233c,struct.pack('<I',0x60010000))
context=bytearray(32);context[0]=1;context[1]=2;context[13]=10
struct.pack_into('<I',context,4,0x3ea150)
u.mem_write(0x60010000,bytes(context));hits.clear()
assert call(0x120d8,(0x613f00,0,0,0))==0
assert hits==[0x5cfb4],hits
report['producer_bridge']={'entry':'0x120d8','bridge':['0x11f84','0x11f68','0x54fec','0x17c608'],'global_gui_context':'0x68233c','state_fixture':2,'selected_action':hex(hits[0]),'delivery':'synchronous native dispatch; no event queue stub'}
Path(n['ROOT'],'sources/native-gui-resume-selection.json').write_text(json.dumps(report,indent=2)+'\n')
print('Stock 120d8 producer -> synchronous GUI dispatch -> 5cfb4 selection verified')
