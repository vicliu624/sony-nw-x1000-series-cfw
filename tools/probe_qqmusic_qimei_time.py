"""Two anonymous bootstrap requests from production ARM request builder.
No account, QR or player access. Raw requests/replies stay in process memory;
reports contain only status, schema and identifier lengths, never identifiers.
"""
from pathlib import Path
import argparse,datetime,email.utils,http.client,json,ssl,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',required=True);p.add_argument('--offset',type=int,required=True);p.add_argument('--single',action='store_true');p.add_argument('--probe-anonymous-service',action='store_true',required=True);a=p.parse_args()
candidate=(ROOT/a.candidate).resolve();assert candidate.is_relative_to(ROOT/'work')
work=ROOT/'work/qqmusic-qimei-time-probe';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';crypto=ROOT/'work/external-tls-probe';app=work/'request.arm'
sources=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('qimei','json','protocol','session','http','cookie','response')]+['runtime/store/'+n+'.c' for n in ('tls_platform','https_url','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]+['runtime/store/start.S','runtime/native/sha256.c','tools/fixtures/qqmusic_qimei_request.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(candidate),'-I'+str(crypto/'bearssl-0.6/inc'),*sources,str(crypto/'arm-build/libbearssl.a'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
rows=[]
for offset in ((a.offset,) if a.single else (a.offset,0)):
 timestamp=int(time.time())+offset
 generated=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app),str(timestamp)],capture_output=True,check=True,timeout=10).stdout
 head,separator,body=generated.partition(b'\r\n\r\n');assert separator
 lines=head.decode('ascii').split('\r\n');method,path,_=lines[0].split(' ',2)
 headers=[line.split(':',1) for line in lines[1:] if line]
 assert method=='POST' and path=='/tme/trpc/proxy' and all(k.lower()!='cookie' for k,v in headers)
 context=ssl.create_default_context();c=http.client.HTTPSConnection('api.tencentmusic.com',timeout=20,context=context)
 try:
  c.putrequest(method,path,skip_host=True,skip_accept_encoding=True)
  for key,value in headers:c.putheader(key,value.strip())
  c.endheaders(body);response=c.getresponse();data=response.read(262145);assert len(data)<=262144
  row={'offset_seconds':offset,'http':response.status,'bytes':len(data),'content_type':response.getheader('Content-Type'),'server_date':response.getheader('Date'),'strict_pc_tls':True}
  try:
   outer=json.loads(data);row['outer_code']=outer.get('code') if isinstance(outer,dict) else None
   inner=outer.get('data') if isinstance(outer,dict) else None;row['data_type']=type(inner).__name__
   if isinstance(inner,str):inner=json.loads(inner)
   if isinstance(inner,dict):
    row['inner_code']=inner.get('code');ids=inner.get('data')
    if isinstance(ids,dict):row['q16_length']=len(ids.get('q16',''));row['q36_length']=len(ids.get('q36',''))
   row['time_related_message']=any(word in str(outer.get('msg','') if isinstance(outer,dict) else '').lower() for word in ('time','expired','timestamp'))
  except (ValueError,TypeError):row['json_shape_accepted']=False
  rows.append(row);print(json.dumps(row),flush=True)
 finally:c.close()
report={'anonymous_service_contacted':True,'account_or_qr_or_player_accessed':False,'raw_payloads_saved':False,'cases':rows}
(work/('single-report.json' if a.single else 'report.json')).write_text(json.dumps(report,indent=2)+'\n')
