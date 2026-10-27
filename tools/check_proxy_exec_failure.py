"""Original proxy child exec failure path; errno/exec/exit are virtual boundaries."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
captured=(ROOT/'sources/native-manager-proxy-exec-request.json').read_bytes();launch=json.loads(captured)
raw=(ROOT/'work/targets-jp/appproxy').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
assert launch['appproxy_sha256']==digest
elf=ELFFile(io.BytesIO(raw));syms={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for case in launch['cases']:
 request=case['proxy_registration']['activation']['captured_frontend_exec_requests'][0]
 for error in (2,8,13):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x60000000,0x10000)
    pointers=[];cursor=0x60001000
    for argument in request['argv']:
        pointers.append(cursor);encoded=argument.encode()+b'\0';u.mem_write(cursor,encoded);cursor+=len(encoded)
    u.mem_write(0x60002000,struct.pack('<'+'I'*(len(pointers)+1),*pointers,0))
    u.mem_write(0x1ca4c,struct.pack('<I',pointers[0]));u.mem_write(0x1ca50,struct.pack('<I',0x60002000))
    u.mem_write(0x60003000,struct.pack('<I',error));exits=[];executions=[]
    def cstr(p):return bytes(u.mem_read(p,256)).split(b'\0')[0].decode()
    def hook(uc,pc,size,data):
        a=uc.reg_read(UC_ARM_REG_R0);b=uc.reg_read(UC_ARM_REG_R1)
        if pc==syms['execvp']:
            assert cstr(a)==request['path'];argv=[]
            for i in range(8):
                pointer=struct.unpack('<I',uc.mem_read(b+4*i,4))[0]
                if not pointer:break
                argv.append(cstr(pointer))
            assert argv==request['argv'];executions.append(argv);result=0xffffffff
        elif pc==syms['__errno_location']:result=0x60003000
        elif pc==syms['exit']:exits.append(a);uc.emu_stop();return
        else:return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_SP,0x60008000)
    u.emu_start(0x9628,0,count=1000)
    assert exits==[error] and len(executions)==1
    rows.append({'target':case['target'],'exec_errno':error,'child_exit':exits[0],'child_wait_status':exits[0]<<8,'captured_argv':request['argv']})
report={'scope':__doc__,'appproxy_sha256':digest,'launch_capture_sha256':hashlib.sha256(captured).hexdigest(),'cases':rows,'physical_device_access':False,'limits':['Child branch starts at original9628 after supplied argv staging; no OS fork/exec occurs.','Missing/invalid/inaccessible file behavior is supplied as execvp failure plus errno; original code selects exit status.']}
(ROOT/'sources/native-proxy-exec-failure.json').write_text(json.dumps(report,indent=2)+'\n')
print('Six original proxy child exec failures: errno2/8/13 become actual child exit codes')
