"""Execute full ARM front end with fake device syscalls and in-memory files.
No Sony program, physical device, real fork, exec or mount is performed.
"""
from pathlib import Path
import io,json,hashlib,struct,argparse,os
from evidence_checks import verify_report
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_SP,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw_path=ROOT/'work/x1000-homebrew-frontend'
if os.environ.get('HB_FRONTEND_BINARY'):
    raw_path=Path(os.environ['HB_FRONTEND_BINARY']).resolve();assert raw_path.is_relative_to(ROOT/'work')
raw=raw_path.read_bytes();elf=ELFFile(io.BytesIO(raw));segments=[s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'];symbols={s.name:s['st_value']for s in elf.get_section_by_name('.symtab').iter_symbols()}
APPROOT='/contents/HOMEBREW/apps'
def cstr(u,p):
    b=bytearray()
    for i in range(1024):
        c=u.mem_read(p+i,1)[0]
        if not c:return b.decode()
        b.append(c)
    raise ValueError('unterminated guest string')
def packet(x,y,down):
    rx=(x*2929+239)//240;ry=((431-y)*5281+431)//432
    b=bytearray(11);b[1]=down;struct.pack_into('>HH',b,2,rx,ry);return bytes(b)

def run_case(name,bad_geometry=False,corrupt=False,stop_child=False,child_branch=False,exec_error=False,wait_error=False,stop_at=None,small_smem=False,submit_error=False,busy_queries=0,stop_busy=False,ignored_query=False,init_error=False,registered_entry=False,launch_argv=None,crowded=False,banner_first=False):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);low=min(s['p_vaddr']for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz']for s in segments)+4095)&~4095;u.mem_map(low,high-low)
    for s in segments:u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x60000000,0x20000);u.mem_map(0x71000000,0xc0000)
    u.mem_write(0x60010000,struct.pack('<5I',2,0x60010100,0x60010120,0,0));u.mem_write(0x60010100,b'frontend\0');u.mem_write(0x60010120,b'--native\0');u.reg_write(UC_ARM_REG_SP,0x60010000)
    if registered_entry:
        u.mem_write(0x60010000,struct.pack('<4I',1,0x60010200,0,0))
        u.mem_write(0x60010200,b'/contents/HOMEBREW/launcher/app\0')
    if launch_argv is not None:
        assert launch_argv in ([APPROOT.rsplit('/apps',1)[0]+'/launcher/app'],[APPROOT.rsplit('/apps',1)[0]+'/launcher/app','--native'])
        cursor=0x60010400;pointers=[]
        for token in launch_argv:
            pointers.append(cursor);encoded=token.encode()+b'\0';u.mem_write(cursor,encoded);cursor+=len(encoded)
        words=[len(pointers),*pointers,0,0]
        u.mem_write(0x60010000,struct.pack('<'+'I'*len(words),*words))
    files={};ids=['demo','store'];opens=[];fds={};nextfd=10;ioctls=[];maps=0;unmaps=0;forks=0;waits=0;scans=0;kills=[];exitcode=None;exec_path=None;signals=[];trace=[]
    if crowded:ids=['demo'+str(i) for i in range(33)]+['store']
    if crowded=='overflow':ids+=['extra'+str(i) for i in range(32)]
    def install(id):
        data=raw
        fields={'api':'1','id':id,'name':id.upper(),'version':'0.1.0','target':'sony-nw-x1000-jp','exec':'app','bytes':str(len(data)),'sha256':hashlib.sha256(data).hexdigest()}
        files[APPROOT+'/'+id+'/app.ini']=('\n'.join(k+'='+v for k,v in fields.items())+'\n').encode();files[APPROOT+'/'+id+'/app']=data
    for id in ids:install(id)
    if corrupt:
        b=bytearray(files[APPROOT+'/store/app']);b[-1]^=1;files[APPROOT+'/store/app']=bytes(b)
    touches=[packet(20,70,1),packet(20,70,0),packet(20,405,1),packet(20,405,0)]
    if banner_first:touches=[packet(20,366,1),packet(20,366,0)]+touches
    queries=0;submitted_pages=[];next_page=1;submits_per_map=0
    def answer(v):u.reg_write(UC_ARM_REG_R0,v&0xffffffff)
    def request_stop():
        assert set(signals)=={2,15}
        u.mem_write(symbols['stop_requested'],struct.pack('<I',1))
    def intr(uc,interrupt,data):
        nonlocal nextfd,maps,unmaps,forks,waits,scans,exitcode,exec_path,queries,next_page,submits_per_map
        pc=uc.reg_read(UC_ARM_REG_PC);ins=struct.unpack('<I',uc.mem_read(pc-4,4))[0];nr=(ins&0xffffff)-0x900000
        a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5]];trace.append(nr)
        if nr==1:exitcode=a[0];uc.emu_stop();return
        if nr==174:
            sa=struct.unpack('<5I',uc.mem_read(a[1],20));assert a[0]in(2,15) and a[3]==8
            if sa[0]==0:
                assert child_branch and forks==1 and sa==(0,0,0,0,0)
            else:
                assert sa[1]==0x04000004
                assert struct.unpack('<I',uc.mem_read(sa[2],4))[0]==0xef9000ad;signals.append(a[0])
            answer(0);return
        if nr==85:
            p=cstr(uc,a[0]);exists=p in files or p==APPROOT or p in [APPROOT+'/'+id for id in ids];answer(-22 if exists else -2);return
        if nr==5:
            p=cstr(uc,a[0]);opens.append(p)
            if p not in files and p not in (APPROOT,'/dev/fb/0','/dev/icx_touch_screen'):answer(-2);return
            fd=nextfd;nextfd+=1;fds[fd]={'path':p,'pos':0}
            if p==APPROOT:scans+=1
            if p=='/dev/fb/0' and stop_at=='fb-open':request_stop()
            answer(fd);return
        if nr==6:assert a[0]in fds;del fds[a[0]];answer(0);return
        if nr==3:
            f=fds[a[0]];b=files[f['path']];out=b[f['pos']:f['pos']+min(a[2],37)];f['pos']+=len(out);uc.mem_write(a[1],out)
            if f['path'].endswith('/app.ini') and ((stop_at=='scan' and scans==1) or (stop_at=='rescan' and scans==2)):request_stop()
            answer(len(out));return
        if nr==19:
            f=fds[a[0]];assert a[2]==2;f['pos']=len(files[f['path']]);answer(f['pos']);return
        if nr==141:
            f=fds[a[0]];assert f['path']==APPROOT
            if f['pos']:answer(-5 if crowded=='read-error' else 0);return
            out=bytearray()
            for id in ['.','..',*ids]:
                b=id.encode()+b'\0';n=(10+len(b)+3)&~3;out+=struct.pack('<IIH',1,0,n)+b+bytes(n-10-len(b))
            if crowded=='bad-dirent':out+=b'\0'*4
            assert len(out)<=a[2];uc.mem_write(a[1],bytes(out));f['pos']=len(out);answer(len(out));return
        if nr==54:
            path=fds[a[0]]['path'];cmd=a[1];ioctls.append(hex(cmd))
            if path=='/dev/fb/0':
                if cmd==0x4602:
                    words=[0]*32;words[5]=240*432*2 if small_smem else 0x120000;words[11]=480;uc.mem_write(a[2],struct.pack('<32I',*words))
                elif cmd==0x4600:
                    words=[0]*40;words[0]=240;words[1]=320 if bad_geometry else 432;words[2]=240;words[3]=864;words[6]=16;words[8]=11;words[9]=5;words[11]=5;words[12]=6;words[15]=5;uc.mem_write(a[2],struct.pack('<40I',*words))
                elif cmd==0x80044e04:
                    assert maps>unmaps and struct.unpack('<2I',uc.mem_read(a[2],8))==(0,33)
                    fds[a[0]]['timeout_initialized']=True
                    if stop_at=='display-init':request_stop()
                    if init_error:answer(-5);return
                elif cmd==0x80044e00:
                    assert fds[a[0]].get('timeout_initialized')
                    assert struct.unpack('<3I',uc.mem_read(a[2],12))==(0,0xffffffff,0xffffffff)
                    queries+=1
                    if ignored_query:answer(0);return
                    busy=stop_busy or queries<=busy_queries
                    words=[0,1,1] if busy else [0,0 if next_page==0 else 1,0 if next_page==1 else 1]
                    uc.mem_write(a[2],struct.pack('<3I',*words))
                    if stop_busy:request_stop()
                elif cmd==0x40044e01:
                    words=list(struct.unpack('<6I',uc.mem_read(a[2],24)))
                    assert words==[1,1,255,next_page,0,0]
                    offset=next_page*0x60000;pixels=240*432*2
                    assert bytes(uc.mem_read(0x71000000+offset,pixels))==bytes(uc.mem_read(symbols['canvas'],pixels))
                    if not submits_per_map:assert bytes(uc.mem_read(0x71000000+(1-next_page)*0x60000,pixels))==b'\xa5'*pixels
                    for start in (0,0x60000):assert bytes(uc.mem_read(0x71000000+start+pixels,0x60000-pixels))==b'\xa5'*(0x60000-pixels)
                    submitted_pages.append(next_page);submits_per_map+=1;next_page=1-next_page
                    if submit_error:answer(-5);return
                else:raise AssertionError('Unexpected framebuffer mutation ioctl')
            elif path=='/dev/icx_touch_screen':
                if cmd==0x80045401:assert touches;uc.mem_write(a[2],touches.pop(0))
                else:assert cmd==0x5404
            else:raise AssertionError(path)
            answer(0);return
        if nr==192:
            assert a[1]==0xc0000 and a[2]==3 and a[3]==1;maps+=1;submits_per_map=0
            uc.mem_write(0x71000000,b'\xa5'*0xc0000);answer(0x71000000);return
        if nr==91:
            assert a[0]==0x71000000 and a[1]==0xc0000;unmaps+=1
            if stop_at=='before-fork' and unmaps==1:request_stop()
            answer(0);return
        if nr==168:
            if not submitted_pages and queries<=busy_queries:answer(0);return
            assert touches,'Event loop failed to finish';assert a[1]==1;uc.mem_write(a[0]+6,struct.pack('<H',1));answer(1);return
        if nr==2:
            if crowded:assert opens[-1]==APPROOT+'/store/app',('First selected item is not store',opens[-1])
            forks+=1
            if stop_at=='fork-child':request_stop()
            answer(0 if child_branch else 321);return
        if nr==57:answer(0);return
        if nr==12:assert cstr(uc,a[0])==APPROOT+'/store';answer(0);return
        if nr==11:
            exec_path=cstr(uc,a[0]);assert exec_path==APPROOT+'/store/app';argv0=struct.unpack('<I',uc.mem_read(a[1],4))[0];assert cstr(uc,argv0)==exec_path;assert not fds
            if exec_error:answer(-8);return
            uc.emu_stop();return
        if nr==114:
            waits+=1;assert a[0]==321
            if waits==1:
                if wait_error:answer(-5);return
                if stop_child:uc.mem_write(symbols['stop_requested'],struct.pack('<I',1))
                answer(0);return
            uc.mem_write(a[1],struct.pack('<I',0))
            if not stop_child and 'newapp'not in ids:ids.append('newapp');install('newapp')
            answer(321);return
        if nr==162:answer(0);return
        if nr==37:kills.append((a[0]-0x100000000 if a[0]&0x80000000 else a[0],a[1]));answer(0);return
        if nr==4:assert a[0]in(1,2),'Unexpected file write';answer(a[2]);return
        raise AssertionError(('unmodeled syscall',nr,a))
    u.hook_add(UC_HOOK_INTR,intr);u.emu_start(elf['e_entry'],0,count=30000000)
    if child_branch and stop_at=='fork-child':assert exec_path is None and exitcode==0 and not fds and maps==unmaps
    elif child_branch:assert exec_path and exitcode==(127 if exec_error else None)
    else:
        assert exitcode==(2 if bad_geometry or small_smem or submit_error or ignored_query or init_error else 0),(name,exitcode)
        assert not fds and maps==unmaps,(name,fds,maps,unmaps)
    if stop_at in ('scan','fb-open'):
        assert maps==forks==0
        if stop_at=='scan':assert not any(p.startswith('/dev/') for p in opens)
    elif stop_at=='before-fork':assert forks==0 and maps==unmaps==1
    elif stop_at=='rescan':assert forks==1 and maps==unmaps==1
    elif stop_at=='fork-child':assert forks==1
    elif stop_at=='display-init':assert forks==0 and maps==unmaps==1 and queries==0 and not submitted_pages
    elif bad_geometry or small_smem:assert maps==forks==0
    elif stop_busy or ignored_query:assert not submitted_pages and forks==0
    elif submit_error or init_error:assert forks==0
    elif corrupt:assert forks==0
    elif stop_child or wait_error:assert kills==[(-321,15)]
    elif not child_branch:
        assert scans>=2
        if not crowded:assert APPROOT+'/newapp/app.ini'in opens,'New app not rescanned after app return'
    assert not any(c in ioctls for c in ['0x40046702','0x40046703']),'USB mode changed'
    return {'case':name,'exit':exitcode,'exec_request':exec_path,'maps':maps,'unmaps':unmaps,'fork_requests':forks,'kill_requests':kills,'all_handles_closed':not fds,'ready_queries':queries,'submitted_pages':submitted_pages,'syscalls':len(trace)}

cases=[run_case('list-app-list-return'),run_case('unsupported-display',bad_geometry=True),run_case('corrupt-app-stays-in-list',corrupt=True),run_case('native-stop-during-child',stop_child=True),run_case('child-exec-contract',child_branch=True),run_case('exec-error-exits-child',child_branch=True,exec_error=True),run_case('wait-error-cleans-child-before-ui',wait_error=True),run_case('stop-during-initial-catalog',stop_at='scan'),run_case('stop-during-framebuffer-open',stop_at='fb-open'),run_case('stop-after-release-before-fork',stop_at='before-fork'),run_case('stop-during-return-catalog',stop_at='rescan'),run_case('inherited-stop-before-child-exec',child_branch=True,stop_at='fork-child')]
cases += [run_case('display-memory-too-small',small_smem=True),run_case('display-submit-fails',submit_error=True),run_case('busy-pages-retry-and-app-return',busy_queries=3),run_case('stop-with-both-pages-busy',stop_busy=True),run_case('unsupported-readiness-query',ignored_query=True)]
cases += [run_case('stock-display-init-fails',init_error=True)]
cases += [run_case('stop-during-stock-display-init',stop_at='display-init')]
cases += [run_case('registered-no-argument-entry-app-list-return',registered_entry=True)]
cases += [run_case('store-found-after-full-list-launches-first',crowded=True)]
cases += [run_case('late-store-child-exec-path',crowded=True,child_branch=True),run_case('late-store-corruption-rejected',crowded=True,corrupt=True)]
cases += [run_case('store-preserved-when-scan-limit-reached',crowded='overflow')]
cases += [run_case('store-preserved-after-directory-read-error',crowded='read-error'),run_case('store-preserved-after-malformed-directory-tail',crowded='bad-dirent')]
cases += [run_case('status-banner-tap-does-not-launch-sixth-app',crowded=True,banner_first=True)]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--proxy-exec-report',action='append',default=[])
parser.add_argument('--second-entry-report',action='append',default=[])
parser.add_argument('--report',help='Optional distinct JSON report under sources/, preserving the standard contract report.')
options=parser.parse_args()
captures=[]
for relative in options.proxy_exec_report:
    path=(ROOT/relative).resolve();assert path.is_relative_to(ROOT/'sources')
    content=path.read_bytes();capture=json.loads(content)
    assert capture['sysmgrd_sha256']=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
    assert capture['appproxy_sha256']=='57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
    assert len(capture['cases'])==(1 if capture.get('home_switch_input') else 2)
    for row in capture['cases']:
        requests=row['proxy_registration']['activation']['captured_frontend_exec_requests'];assert len(requests)==1
        request=requests[0];assert request['path']=='/contents/HOMEBREW/launcher/app'
        result=run_case('captured-proxy-'+row['target']+'-'+str(len(request['argv'])),launch_argv=request['argv'])
        result['captured_argv']=request['argv'];cases.append(result)
    captures.append({'path':relative,'sha256':hashlib.sha256(content).hexdigest()})
for relative in options.second_entry_report:
    path=(ROOT/relative).resolve();assert path.is_relative_to(ROOT/'sources')
    capture=verify_report(ROOT,relative);activation=capture['second_proxy_activation']
    assert activation['proxy_state']==activation['manager_record_state']==2 and activation['stopped_before_exec']
    requests=activation['captured_frontend_exec_requests'];assert len(requests)==1
    request=requests[0];assert request['path']=='/contents/HOMEBREW/launcher/app'
    result=run_case('second-entry-captured-proxy',launch_argv=request['argv'])
    assert result['exit']==0 and result['all_handles_closed'] and result['maps']==result['unmaps']
    result['captured_argv']=request['argv'];result['capture_phase']='second-entry';cases.append(result)
    captures.append({'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'scope':'actual experimental ARM front end; virtual files/devices/children/signals only','program_sha256':hashlib.sha256(raw).hexdigest(),'cases':cases,'physical_device_access':False,'Sony_handoff_validated':False}
report['proxy_capture_inputs']=captures
output=ROOT/('sources/native-proxy-frontend-contract.json' if captures else 'sources/native-adapter-tests.json')
if options.report:
    output=(ROOT/options.report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
    report['all_bounded_checks_passed']=True
    report.update({'artifact':str(raw_path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    report['source_hashes']={item['path']:item['sha256'] for item in captures}
    report['source_hashes']['tools/test_native_adapter.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
