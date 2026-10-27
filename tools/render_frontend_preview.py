"""Render actual ARM frontend pixels to PNG with fixture catalogs; no device/UI access."""
from pathlib import Path
import hashlib,json,struct,subprocess,zlib
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('frontend-preview-'+version);area.mkdir(exist_ok=True)
binary=ROOT/'work/x1000-homebrew-frontend';payload=binary.read_bytes();digest=hashlib.sha256(payload).hexdigest()
def chunk(kind,content):return struct.pack('>I',len(content))+kind+content+struct.pack('>I',zlib.crc32(kind+content)&0xffffffff)
def png(raw):
    assert len(raw)==240*432*2
    rows=[]
    for y in range(432):
        rgb=bytearray([0])
        for x in range(240):
            pixel=struct.unpack_from('<H',raw,(y*240+x)*2)[0]
            rgb.extend(((pixel>>11)*255//31,((pixel>>5)&63)*255//63,(pixel&31)*255//31))
        rows.append(rgb)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
results=[]
for profile,labels in [('empty',[]),('six-rows',['STORE FIXTURE','DEMO ONE','DEMO TWO','DEMO THREE','DEMO FOUR','SIXTH ROW'])]:
    catalog=area/profile;catalog.mkdir(exist_ok=True)
    for i,label in enumerate(labels):
        app_id='store' if i==0 else 'demo'+str(i);folder=catalog/app_id;folder.mkdir(exist_ok=True)
        (folder/'app').write_bytes(payload)
        fields={'api':'1','id':app_id,'name':label,'version':'0.0.0','target':'sony-nw-x1000-jp','exec':'app','bytes':str(len(payload)),'sha256':digest}
        (folder/'app.ini').write_text('\n'.join(key+'='+value for key,value in fields.items())+'\n')
    result=subprocess.run(['qemu-arm','-cpu','arm926',str(binary),'--render',str(catalog)],capture_output=True,check=True,timeout=30)
    output=area/(profile+'.png');output.write_bytes(png(result.stdout))
    results.append({'fixture':profile,'image':output.relative_to(ROOT).as_posix(),'frame_sha256':hashlib.sha256(result.stdout).hexdigest()})
(area/'provenance.json').write_text(json.dumps({'version':version,'program_sha256':digest,'screens':results,'scope':'Actual C/ARM framebuffer output; fixture apps only, not real store/apps or physical display'},indent=2)+'\n')
print(json.dumps(results,indent=2))
