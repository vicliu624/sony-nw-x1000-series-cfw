"""Execute the stock tuning body and ioctl wrapper with a simulated register bus."""
import contextlib,io,runpy,struct,json
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_PC
with contextlib.redirect_stdout(io.StringIO()):ctx=runpy.run_path(str(Path(__file__).with_name('check_fm_ioctl.py')))
elf=ctx['elf'];images=ctx['images'];sections=ctx['sections'];symbols=ctx['symbols'];external=ctx['external'];rows=[]
for mode in ['complete','timeout','write-failure','read-failure']:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for i,base in sections.items():
  size=elf.get_section(i)['sh_size'];u.mem_map(base,max(4096,(size+4095)&~4095))
  if i in images:u.mem_write(base,bytes(images[i]))
 for base in [0x700000,0x800000,0x900000,0xa00000]:u.mem_map(base,0x10000)
 file,dev,state,arg=0x801000,0x802000,0x803000,0x804000
 u.mem_write(file+128,struct.pack('<I',0x805000));u.mem_write(dev+64,struct.pack('<I',state));u.mem_write(state,struct.pack('<5I',76000,1,0,6,0));u.mem_write(arg,struct.pack('<I',82500*16))
 events=[];registers={2:0x4001,5:0x50,10:0x4000 if mode=='complete' else 0};visited=[]
 helpers={symbols[n]:n for n in ['video_devdata','si470x_read','si470x_write','msleep','__udivsi3','printk','icx1087_AdcMixMute']}
 def hook(uc,pc,size,data):
  if pc==0xa00000:uc.emu_stop();return
  if pc==symbols['fmSetFreq']:visited.append('fmSetFreq')
  if pc in external.values() and pc not in helpers:raise AssertionError(('unexpected helper',hex(pc),[n for n,a in external.items() if a==pc]))
  if pc not in helpers:return
  name=helpers[pc];a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]
  if name=='video_devdata':result=dev
  elif name=='si470x_read':result=0xffffffff if mode=='read-failure' else registers.get(a[1],0);events.append({'read':a[1],'value':result})
  elif name=='si470x_write':
   events.append({'write':a[1],'value':a[2]});result=0xffffffff if mode=='write-failure' and a[1]==3 else 0
   if not result:registers[a[1]]=a[2]
  elif name=='msleep':events.append({'sleep_ms':a[0]});result=0
  elif name=='icx1087_AdcMixMute':events.append({'adc_mix_mute_argument':a[0]});result=0
  elif name=='__udivsi3':assert a[1];result=a[0]//a[1]
  else:events.append({'diagnostic':True});result=0
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in [(UC_ARM_REG_R0,0x800000),(UC_ARM_REG_R1,file),(UC_ARM_REG_R2,0x4004760f),(UC_ARM_REG_R3,arg),(UC_ARM_REG_SP,0x90f000),(UC_ARM_REG_LR,0xa00000)]:u.reg_write(reg,value)
 u.emu_start(symbols['fm_do_ioctl'],0,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0xa00000 and visited==['fmSetFreq']
 result=u.reg_read(UC_ARM_REG_R0);fields=list(struct.unpack('<5I',u.mem_read(state,20)))
 assert result==0 and fields[0]==82500
 if mode=='complete':assert fields[4]==1 and registers[3]&1023==65
 elif mode in ['timeout','write-failure']:assert fields[4]==0
 # A read failure returns all ones, whose STC bit is set: the stock function
 # can misinterpret bus failure as completion. Our transport rejects 0xffff.
 elif mode=='read-failure':assert fields[4]==1
 rows.append({'mode':mode,'ioctl_return':result,'cached_khz':fields[0],'internal_tuned_field':fields[4],'events':events})
report={'passed':True,'module_sha256':ctx['ctx']['hashlib'].sha256(ctx['module']).hexdigest(),'cases':rows,'scope':'Original fm_do_ioctl, fmSetFreq and mute helpers execute; register bus, msleep, unsigned division, printk, ADC mixer mute and video_devdata are replacements.','hardware_tested':False,'limits':['Completion under a simulated bus does not prove hardware lock or sound.','Driver accepts bus-read failure all-ones as a set completion bit; native transport must reject it.','Tuning requests can block inside the original ioctl; user cancellation cannot interrupt every kernel phase.']}
(ctx['work']/'tune-completion.json').write_text(json.dumps(report,indent=2)+'\n');print('Original FM tune replay: complete, timeout, write failure and read failure checked.')
