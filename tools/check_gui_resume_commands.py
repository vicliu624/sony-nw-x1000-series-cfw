"""Replay stock command routing up to the restore helper, with explicit GUI gate fixtures."""
import runpy,json,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')))
u=n['u'];call=n['call'];gate=0;selected=[]
def hook(uc,pc,size,data):
 if pc in (0x120ec,0x14560,0x1483c,0x147a8,0x145b8,0x145dc,0x1469c,0x1470c,0x1477c,0x144d4,0x145e8,0x145fc,0x145c0,0x14650,0x147b8):
  selected.append(pc);uc.reg_write(UC_ARM_REG_PC,0x50000000);return
 if pc in (0x116d4,0x33b83c):
  uc.reg_write(UC_ARM_REG_R0,0)
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
h=u.hook_add(UC_HOOK_CODE,hook);rows=[]
for gate in (0,1):
 for command in range(1,22):
  u.mem_write(0x613f00+0x5eb0,struct.pack('<I',gate));selected.clear();call(0x143c0,(0x613f00,command,0x60011000,0))
  assert len(selected)==1
  rows.append({'gui_gate_fixture':gate,'command':command,'boundary':hex(selected[0]),'reaches_restore_helper':selected[0]==0x120ec})
restore=[r for r in rows if r['reaches_restore_helper']]
assert [(r['gui_gate_fixture'],r['command']) for r in restore]==[(0,7),(0,21)]
r={'scope':'Native command selector; GUI gate executes native field read; log helpers virtual; stops before restore helper or other branch body','SpiderApp_sha256':n['digest'],'cases':rows,'restore_routes':restore,'limits':['Gate values are fixtures, not proof of APF return state.','No full coordinator, restoration or hardware execution.']}
Path(n['ROOT'],'sources/native-gui-resume-command-routing.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(restore,indent=2))

